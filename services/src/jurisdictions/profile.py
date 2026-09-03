"""Contrato de un perfil de jurisdicción (ADR-0008).

Todo lo que depende del país vive en un perfil y en ningún otro lugar del código.
La razón no es de estilo: un literal paraguayo olvidado en un módulo compartido no
rompe una prueba, **emite un certificado que afirma algo falso sobre una persona**.

Un perfil describe seis cosas:

1. **Qué norma se cita** en la constancia que se entrega al firmante.
2. **Cómo se identifica** a una persona: qué documentos se admiten y con qué formato.
3. **Cómo se la nombra** en el certificado X.509 (país y `serialNumber`).
4. **Cuánto se conserva** la evidencia, y desde cuándo cuenta el plazo.
5. **Qué actos jurídicos** no admiten firma electrónica no cualificada.
6. **Ante quién se responde**: autoridad reguladora, plazo de notificación de
   incidentes y catálogo de autoridades de sellado de tiempo aceptadas.

Los perfiles son inmutables y se cargan una sola vez: son configuración, no estado.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType


@dataclass(frozen=True, slots=True)
class DocumentType:
    """Un tipo de documento de identidad admitido por la jurisdicción."""

    #: Identificador estable que viaja en la evidencia (por ejemplo ``CI_PY``).
    code: str
    #: Nombre para mostrar al firmante, en el idioma de la jurisdicción.
    label: str
    #: Expresión regular que valida el número. Debe anclarse en ambos extremos.
    pattern: str
    #: Sigla que precede al número en el ``serialNumber`` del sujeto del
    #: certificado. La fija el perfil de certificado de la jurisdicción, no el
    #: código interno: el validador que lee un certificado distingue una cédula de
    #: un pasaporte por esta sigla, y una equivocada afirma un tipo de documento
    #: que el titular no presentó.
    certificate_prefix: str = ""

    def matches(self, national_id: str) -> bool:
        return re.fullmatch(self.pattern, national_id) is not None


@dataclass(frozen=True, slots=True)
class TimestampAuthority:
    """Autoridad de sellado de tiempo admitida en la jurisdicción."""

    name: str
    #: ``True`` solo si un prestador cualificado la opera bajo la norma local. Una
    #: TSA de otro país es válida criptográficamente y discutible jurídicamente.
    qualified: bool
    url: str = ""


@dataclass(frozen=True, slots=True)
class Regulator:
    """Autoridad ante la que se responde y plazos que impone."""

    name: str
    short_name: str
    contact: str
    #: Plazo máximo para notificar un incidente de seguridad.
    incident_notification_hours: int
    #: Equipo de respuesta a incidentes que también debe ser notificado.
    incident_response_team: str = ""


@dataclass(frozen=True, slots=True)
class EvidenceRetention:
    """Plazo mínimo de conservación de la evidencia."""

    minimum_days: int
    #: Desde cuándo corre el plazo, en los términos de la norma.
    counted_from: str
    legal_basis: str

    def __post_init__(self) -> None:
        if self.minimum_days < 365:
            raise ValueError(
                "Un plazo de conservación inferior a un año no es admisible para "
                "evidencia con valor probatorio."
            )


@dataclass(frozen=True, slots=True)
class LegalActRestrictions:
    """Actos jurídicos excluidos de la firma electrónica no cualificada.

    La distinción entre bloqueo y advertencia es deliberada: se prefiere el falso
    positivo —bloquear y exigir revisión humana— sobre el falso negativo, que
    produce un documento inválido y un pasivo para la plataforma y su cliente.
    """

    #: Términos que bloquean la firma. Normalizados: minúsculas y sin acentos.
    excluded: frozenset[str]
    #: Términos que exigen revisión humana pero no bloquean.
    warning: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class JurisdictionProfile:
    """Perfil completo de una jurisdicción."""

    #: Código ISO 3166-1 alfa-2 en mayúsculas.
    code: str
    name: str

    #: Norma citada en la constancia entregada al firmante.
    signature_law_citation: str
    #: Norma que da validez a la firma electrónica no cualificada.
    signature_law_name: str

    document_types: tuple[DocumentType, ...]
    #: Prefijo de la clave del índice pericial por firmante. **No viaja en el
    #: certificado**: es un identificador interno que solo desambigua entre países.
    signer_index_prefix: str
    #: Valor del atributo ``C`` (país) del sujeto del certificado.
    certificate_country: str
    #: Valor literal del atributo ``O`` del sujeto, tal como lo fija el perfil de
    #: certificado de la jurisdicción. No es el nombre del prestador: el perfil
    #: paraguayo lo usa para declarar **qué clase de certificado es**.
    certificate_subject_organization: str
    #: Valor literal del atributo ``OU`` del sujeto: la descripción del tipo de
    #: certificado que fija el perfil.
    certificate_subject_organizational_unit: str

    retention: EvidenceRetention
    restrictions: LegalActRestrictions
    regulator: Regulator
    timestamp_authorities: tuple[TimestampAuthority, ...]

    #: Textos de producto de la jurisdicción, indexados por clave.
    texts: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))

    #: ``False`` mientras el perfil no haya sido revisado por asesoría legal local.
    #: Un perfil sin validar sirve para probar que la arquitectura generaliza; el
    #: servicio se niega a operar con él fuera de desarrollo.
    legally_validated: bool = False

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z]{2}", self.code):
            raise ValueError(f"El código de jurisdicción debe ser ISO alfa-2: {self.code!r}")
        if not self.document_types:
            raise ValueError(f"La jurisdicción {self.code} no declara ningún documento admitido")

    # ------------------------------------------------------------- Identidad --
    def document_type(self, code: str) -> DocumentType:
        for tipo in self.document_types:
            if tipo.code == code:
                return tipo
        raise ValueError(
            f"El documento {code!r} no está admitido en la jurisdicción {self.code}. "
            f"Admitidos: {', '.join(t.code for t in self.document_types)}"
        )

    def validate_national_id(self, document_type: str, national_id: str) -> None:
        """Comprueba que el número corresponde al formato del documento declarado."""
        tipo = self.document_type(document_type)
        if not tipo.matches(national_id):
            raise ValueError(f"El número no tiene el formato de {tipo.label} en {self.name}.")

    def subject_serial_number(self, national_id: str, *, document_type: str) -> str:
        """Valor del ``serialNumber`` del sujeto en el certificado X.509.

        Lo compone la **sigla del tipo de documento** seguida del número, y no el
        código del país. Es lo que el perfil de certificado exige, y tiene una
        razón: el ``serialNumber`` es el campo por el que un validador identifica
        unívocamente al titular, y la sigla es lo que distingue una cédula de un
        pasaporte. Un prefijo de país deja los dos indistinguibles.
        """
        tipo = self.document_type(document_type)
        if not tipo.certificate_prefix:
            raise ValueError(
                f"El documento {document_type!r} de la jurisdicción {self.code} no declara "
                "la sigla que debe llevar el `serialNumber` del certificado."
            )
        return f"{tipo.certificate_prefix}{national_id}"

    @property
    def default_document_type(self) -> DocumentType:
        """Documento que se asume cuando el inquilino no declara cuál presentó.

        Es el primero del catálogo. La suposición es visible a propósito: emitir un
        certificado que afirma «cédula» sobre el número de un pasaporte es
        exactamente la clase de afirmación falsa que el perfil existe para evitar,
        de modo que el inquilino debería declararlo siempre que pueda.
        """
        return self.document_types[0]

    def signer_index_key(self, national_id: str) -> str:
        """Clave de partición del índice por firmante en la pista de auditoría.

        Lleva el código de la jurisdicción porque dos países pueden emitir el mismo
        número de documento a personas distintas: sin él, el índice pericial
        mezclaría a dos firmantes bajo una sola clave.
        """
        return f"CI#{self.signer_index_prefix}-{national_id}"

    # ----------------------------------------------------------------- Texto --
    def text(self, key: str) -> str:
        try:
            return self.texts[key]
        except KeyError as exc:
            raise KeyError(f"La jurisdicción {self.code} no define el texto {key!r}.") from exc

    def qualified_timestamp_authorities(self) -> tuple[TimestampAuthority, ...]:
        return tuple(t for t in self.timestamp_authorities if t.qualified)
