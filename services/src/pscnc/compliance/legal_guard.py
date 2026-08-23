"""Agente regulatorio: bloqueo de actos jurídicos excluidos de la FENC.

La firma electrónica no cualificada goza de validez jurídica por el principio de
no discriminación, pero **no sustituye la forma solemne** cuando la ley la exige
(escritura pública, presencia notarial, actos de derecho de familia y sucesorio).
Firmar uno de esos actos con una FENC no produce un documento válido: produce un
pasivo legal para la plataforma y para su cliente B2B.

Este módulo materializa esa frontera. La lista de exclusiones es **configurable y
debe ser revisada y aprobada por asesoría legal paraguaya** antes de producción;
su historial en el control de versiones constituye evidencia de diligencia.

Limitación conocida y deliberada: la detección es léxica y no sustituye la
revisión legal del cliente B2B. Se prefiere el falso positivo (bloquear y exigir
revisión humana) sobre el falso negativo (firmar un acto excluido).
"""

from __future__ import annotations

import io
import re
import unicodedata
from dataclasses import dataclass, field

from pscnc.errors import BiometricThresholdError, LegallyExcludedDocumentError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

# Términos que indican actos con forma solemne o excluidos de la firma simple.
# Revisión legal obligatoria antes de cada modificación.
EXCLUSIONES_POR_DEFECTO: frozenset[str] = frozenset(
    {
        "testamento",
        "acto de ultima voluntad",
        "sucesion",
        "hipoteca",
        "prenda con registro",
        "donacion",
        "escritura publica",
        "compraventa de inmueble",
        "transferencia de inmueble",
        "usufructo",
        "matrimonio",
        "capitulaciones matrimoniales",
        "divorcio",
        "adopcion",
        "reconocimiento de filiacion",
        "poder general",
        "poder especial para juicios",
        "constitucion de sociedad anonima",
        "cesion de derechos hereditarios",
        "fideicomiso",
    }
)

# Términos que exigen revisión humana pero no bloquean automáticamente.
ADVERTENCIAS_POR_DEFECTO: frozenset[str] = frozenset(
    {
        "aval",
        "fianza solidaria",
        "pagare",
        "contrato de trabajo",
        "renuncia de derechos",
        "confesion de deuda",
    }
)

MAX_CARACTERES_ANALIZADOS = 200_000


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y con espacios colapsados, para comparación léxica."""
    sin_acentos = "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(caracter) != "Mn"
    )
    return re.sub(r"\s+", " ", sin_acentos)


@dataclass(frozen=True, slots=True)
class ComplianceVerdict:
    """Resultado del análisis de un documento."""

    allowed: bool
    blocking_terms: tuple[str, ...] = ()
    warning_terms: tuple[str, ...] = ()
    extracted_characters: int = 0
    text_extraction_succeeded: bool = True

    @property
    def requires_human_review(self) -> bool:
        return bool(self.warning_terms) or not self.text_extraction_succeeded


@dataclass(slots=True)
class LegalGuard:
    """Evalúa si un documento puede firmarse con una FENC."""

    excluded_terms: frozenset[str] = field(default=EXCLUSIONES_POR_DEFECTO)
    warning_terms: frozenset[str] = field(default=ADVERTENCIAS_POR_DEFECTO)
    block_on_extraction_failure: bool = False

    # ------------------------------------------------------------------ API --
    def evaluate_text(self, texto: str) -> ComplianceVerdict:
        """Analiza texto ya extraído."""
        normalizado = normalizar(texto)[:MAX_CARACTERES_ANALIZADOS]

        bloqueos = tuple(sorted(t for t in self.excluded_terms if t in normalizado))
        advertencias = tuple(sorted(t for t in self.warning_terms if t in normalizado))

        return ComplianceVerdict(
            allowed=not bloqueos,
            blocking_terms=bloqueos,
            warning_terms=advertencias,
            extracted_characters=len(normalizado),
        )

    def evaluate_pdf(self, pdf_bytes: bytes) -> ComplianceVerdict:
        """Extrae el texto del PDF y lo evalúa.

        Un PDF escaneado sin capa de texto no puede analizarse léxicamente. Por
        defecto no se bloquea, pero el veredicto se marca para revisión humana y
        queda registrado en la evidencia.
        """
        try:
            texto = self._extraer_texto(pdf_bytes)
        except Exception as exc:
            logger.warning("pdf_text_extraction_failed", error=str(exc))
            if self.block_on_extraction_failure:
                raise LegallyExcludedDocumentError(
                    "No se pudo analizar el contenido del documento y la política "
                    "vigente exige análisis previo a la firma."
                ) from exc
            return ComplianceVerdict(
                allowed=True,
                extracted_characters=0,
                text_extraction_succeeded=False,
            )

        return self.evaluate_text(texto)

    def enforce(self, verdict: ComplianceVerdict, *, transaction_id: str = "") -> None:
        """Aplica el veredicto: lanza una excepción si el documento está excluido."""
        if verdict.allowed:
            if verdict.requires_human_review:
                logger.info(
                    "compliance_review_suggested",
                    transaction_id=transaction_id,
                    warning_terms=list(verdict.warning_terms),
                    text_extracted=verdict.text_extraction_succeeded,
                )
            return

        logger.warning(
            "compliance_block",
            transaction_id=transaction_id,
            blocking_terms=list(verdict.blocking_terms),
        )
        raise LegallyExcludedDocumentError(
            "El documento contiene indicios de un acto jurídico que requiere forma "
            "solemne o está excluido de la firma electrónica no cualificada. "
            "La operación se bloquea conforme a la política de uso del servicio.",
            detail={"blocking_terms": list(verdict.blocking_terms)},
        )

    # -------------------------------------------------------------- Interno --
    @staticmethod
    def _extraer_texto(pdf_bytes: bytes) -> str:
        from pypdf import PdfReader

        lector = PdfReader(io.BytesIO(pdf_bytes))
        partes: list[str] = []
        for pagina in lector.pages:
            partes.append(pagina.extract_text() or "")
            if sum(len(p) for p in partes) > MAX_CARACTERES_ANALIZADOS:
                break
        return "\n".join(partes)


def enforce_biometric_threshold(
    facial_match_score: float,
    *,
    minimum: float,
    liveness_detected: bool,
    transaction_id: str = "",
) -> None:
    """Verifica el umbral biométrico exigido antes de habilitar la firma.

    Un onboarding aprobado con un puntaje por debajo del umbral declarado en la
    DPSC invalida la cadena probatoria completa: la firma no debe producirse.
    """
    if not liveness_detected:
        logger.warning("liveness_missing", transaction_id=transaction_id)
        raise BiometricThresholdError(
            "El onboarding no acredita prueba de vida activa; no puede firmarse."
        )
    if facial_match_score < minimum:
        logger.warning(
            "biometric_threshold_not_met",
            transaction_id=transaction_id,
            score=round(facial_match_score, 4),
            minimum=minimum,
        )
        raise BiometricThresholdError(
            "La coincidencia biométrica del onboarding es inferior al umbral exigido "
            "por la Declaración de Prácticas del prestador.",
            detail={"minimum_required": minimum},
        )
