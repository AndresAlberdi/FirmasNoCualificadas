"""Motor de firma PAdES-B-T sobre pyHanko.

Puntos que gobiernan este módulo:

* La firma se aplica como **actualización incremental**: los bytes originales del
  PDF no se reescriben, de modo que las firmas previas de terceros —incluidas las
  cualificadas— permanecen íntegras y verificables.
* La operación CMS se realiza con la clave **efímera del firmante**, que vive en
  memoria del proceso. La clave de la CA en KMS solo firma el certificado.
* El sellado de tiempo es obligatorio (nivel mínimo PAdES-B-T).

El nivel PAdES-B-LTA (diccionario ``/DSS`` y archive timestamp) está declarado
como deuda técnica en ``docs/ARQUITECTURA.md §7``.
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, replace
from typing import Any

from jurisdictions import JurisdictionProfile
from pscnc.crypto.constancia import (
    ALTO_MINIMO,
    ANCHO_MINIMO,
    ConstanciaFirma,
    componer_bloque,
)
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, IssuedCertificate, SubjectData
from pscnc.crypto.tsa import RecordingTimeStamper, TimestampResult
from pscnc.errors import DocumentIntegrityError, SigningError, TimestampError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VisualSignatureSpec:
    """Ubicación y tamaño de la representación visual de la firma."""

    enabled: bool = True
    page: int = 1  # 1-indexado, como lo ve el usuario
    x: float = 100.0
    y: float = 150.0
    width: float = 180.0
    height: float = 60.0
    #: Bloque de constancia a imprimir dentro del campo. Si viene, la apariencia
    #: deja de ser un rótulo y pasa a ser el bloque completo con su QR.
    constancia: ConstanciaFirma | None = None

    def con_espacio_para_la_constancia(self) -> VisualSignatureSpec:
        """Agranda la caja si hace falta para que el bloque no se recorte.

        Un bloque recortado es peor que ninguno: deja a la vista media huella y
        media declaración, y las dos cosas dejan de significar lo que dicen.
        """
        if self.constancia is None:
            return self
        return replace(
            self,
            width=max(self.width, ANCHO_MINIMO),
            height=max(self.height, ALTO_MINIMO),
        )

    @property
    def box(self) -> tuple[int, int, int, int]:
        """Caja del campo de firma en puntos PDF, redondeada a entero.

        pyHanko exige enteros. La fracción de punto (1/72 de pulgada) no tiene
        efecto visible y la API pública conserva los valores en coma flotante.
        """
        return (
            round(self.x),
            round(self.y),
            round(self.x + self.width),
            round(self.y + self.height),
        )


@dataclass(frozen=True, slots=True)
class SignatureResult:
    """Producto de una operación de firma, listo para auditoría y entrega."""

    signed_pdf: bytes
    original_sha256: str
    signed_sha256: str
    certificate: IssuedCertificate
    timestamp: TimestampResult
    signature_format: str = "PAdES-B-T"


def sha256_hex(data: bytes) -> str:
    """Huella SHA-256 en hexadecimal minúscula."""
    return hashlib.sha256(data).hexdigest()


class PadesSigner:
    """Aplica una firma PAdES-B-T incremental sobre un documento PDF."""

    def __init__(
        self,
        *,
        certificate_authority: EphemeralCertificateAuthority,
        timestamper_factory: Any,
        jurisdiction: JurisdictionProfile,
    ) -> None:
        self._ca = certificate_authority
        self._timestamper_factory = timestamper_factory
        # El motivo y el lugar quedan impresos en el panel de firma del PDF y los
        # lee cualquier validador: citan la norma de la jurisdicción, no una
        # constante (ADR-0008).
        self._reason = jurisdiction.text("firma.motivo")
        self._location = jurisdiction.text("firma.lugar")
        # El perfil se conserva entero: el bloque de constancia toma de él sus
        # rótulos y su declaración de consentimiento.
        self._jurisdiction = jurisdiction

    def sign(
        self,
        pdf_bytes: bytes,
        subject: SubjectData,
        *,
        visual: VisualSignatureSpec | None = None,
        field_name: str = "FirmaFENC",
    ) -> SignatureResult:
        """Firma el documento y devuelve el binario resultante con su evidencia.

        La clave privada efímera se descarta al terminar: no se persiste, no se
        registra y no se devuelve fuera de este proceso.
        """
        if not pdf_bytes.startswith(b"%PDF-"):
            raise DocumentIntegrityError("El archivo recibido no es un PDF válido")

        original_hash = sha256_hex(pdf_bytes)
        emitido = self._ca.issue(subject)
        timestamper = self._timestamper_factory()

        firmado = self._apply_signature(
            pdf_bytes,
            emitido,
            timestamper=timestamper,
            visual=(visual or VisualSignatureSpec()).con_espacio_para_la_constancia(),
            field_name=field_name,
        )

        signed_hash = sha256_hex(firmado)
        if signed_hash == original_hash:
            raise SigningError(
                "El documento resultante es idéntico al original: la firma no se aplicó"
            )

        resultado_tsa = timestamper.last_result

        logger.info(
            "pades_signature_applied",
            transaction_id=subject.transaction_id,
            certificate_serial=emitido.serial_number,
            tsa_provider=resultado_tsa.provider_name,
            tsa_serial=resultado_tsa.serial_number,
            original_sha256=original_hash,
            signed_sha256=signed_hash,
        )

        return SignatureResult(
            signed_pdf=firmado,
            original_sha256=original_hash,
            signed_sha256=signed_hash,
            certificate=emitido,
            timestamp=resultado_tsa,
        )

    # -------------------------------------------------------------- Interno --
    def _estilo_de_sello(self, visual: VisualSignatureSpec) -> Any:
        """Estilo de la apariencia del campo de firma.

        Sin constancia devuelve ``None`` y pyHanko usa su apariencia por defecto.
        Con constancia, la apariencia **es** el bloque: los datos que el firmante
        y un tercero necesitan leer sin abrir ningún panel, más un QR con la
        dirección de la constancia pública.

        El QR no es adorno. La huella se imprime abreviada para que entre; el
        valor completo vive en la constancia, y el QR es lo que lleva hasta ella
        sin obligar a nadie a transcribir sesenta y cuatro caracteres.
        """
        if visual.constancia is None:
            return None

        from pyhanko.pdf_utils import text as pdf_text
        from pyhanko.stamp import QRStampStyle

        # `%(url)s` queda fuera del texto a propósito: la dirección ya está en el
        # QR, y repetirla en letra chica no ayuda a nadie. pyHanko exige que el
        # parámetro exista igual, y se lo pasa `_apply_signature`.
        return QRStampStyle(
            stamp_text=componer_bloque(visual.constancia, self._jurisdiction),
            text_box_style=pdf_text.TextBoxStyle(font_size=7),
        )

    def _apply_signature(
        self,
        pdf_bytes: bytes,
        emitido: IssuedCertificate,
        *,
        timestamper: RecordingTimeStamper,
        visual: VisualSignatureSpec,
        field_name: str,
    ) -> bytes:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.sign import fields, signers
        from pyhanko.sign.fields import SigSeedSubFilter

        # Desde pyHanko 0.25 el almacén de certificados vive en el validador;
        # el pyproject ya exige esa versión mínima, así que no hay que sondear.
        from pyhanko_certvalidator.registry import SimpleCertificateStore

        # `from_certs` no está anotada en el validador de pyHanko.
        cert_registry = SimpleCertificateStore.from_certs(  # type: ignore[no-untyped-call]
            [self._ca.ca_certificate]
        )
        signer = signers.SimpleSigner(
            signing_cert=emitido.certificate,
            signing_key=emitido.private_key_info,
            cert_registry=cert_registry,
        )

        metadata = signers.PdfSignatureMetadata(
            field_name=field_name,
            # PAdES exige el subfiltro ETSI.CAdES.detached.
            subfilter=SigSeedSubFilter.PADES,
            md_algorithm="sha256",
            reason=self._reason,
            location=self._location,
            embed_validation_info=False,  # nivel B-T; el LTA se incorporará más adelante
            use_pades_lta=False,
        )

        field_spec = None
        if visual.enabled:
            field_spec = fields.SigFieldSpec(
                sig_field_name=field_name,
                box=visual.box,
                on_page=max(visual.page - 1, 0),  # pyHanko usa índice base 0
            )

        pdf_signer = signers.PdfSigner(
            signature_meta=metadata,
            signer=signer,
            timestamper=timestamper,
            new_field_spec=field_spec,
            stamp_style=self._estilo_de_sello(visual),
        )

        entrada = io.BytesIO(pdf_bytes)
        salida = io.BytesIO()
        try:
            writer = IncrementalPdfFileWriter(entrada)
            pdf_signer.sign_pdf(
                writer,
                output=salida,
                in_place=False,
                appearance_text_params=(
                    {"url": visual.constancia.url_verificacion}
                    if visual.constancia is not None
                    else None
                ),
            )
        except TimestampError:
            # El fallo del sellado se deja pasar tal cual, sin envolverlo: la causa
            # es lo que decide qué puede hacer el llamador. Una autoridad de
            # sellado caída es transitoria y admite reintento; un fallo al
            # construir la firma, no. Envolver ambos en el mismo error obligaría a
            # tratarlos igual, y el tenant no puede distinguirlos por el mensaje.
            logger.error("pades_timestamp_failed")
            raise
        except Exception as exc:
            logger.error("pades_signature_failed", error=str(exc))
            raise SigningError("No se pudo aplicar la firma PAdES al documento") from exc

        return salida.getvalue()


def build_timestamper_factory(
    *,
    url: str,
    provider_name: str,
    username: str = "",
    password: str = "",
    timeout: int = 10,
    max_retries: int = 3,
    qualified: bool = True,
) -> Any:
    """Construye una fábrica de selladores: uno nuevo por transacción.

    Se crea uno por firma para que el token retenido corresponda inequívocamente
    a esa transacción y no pueda contaminarse entre peticiones concurrentes.
    """

    def _factory() -> RecordingTimeStamper:
        return RecordingTimeStamper(
            url,
            provider_name=provider_name,
            qualified=qualified,
            username=username or None,
            password=password or None,
            timeout=timeout,
            max_retries=max_retries,
        )

    return _factory
