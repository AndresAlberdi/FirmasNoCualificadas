"""Contrato público de la API v1 (ADR-0007, ADR-0009).

Tres decisiones de este contrato merecen leerse antes de tocarlo, porque parecen
detalles y son lo que hace que la integración sea correcta:

**1. FNC no vuelve a decidir la identidad.** Recibe la decisión que el tenant ya
tomó y la asienta como evidencia. Dos controles de identidad sobre el mismo acto
no se suman: gana el más laxo. Si FNC aprobara con su propio umbral lo que la
política del tenant rechaza, no estaría agregando una garantía — estaría anulando
la del tenant.

**2. El OTP del tenant es evidencia, no control.** El OTP prueba la voluntad de
firmar *ante el tenant*, que es con quien la persona contrata. Reverificarlo acá
no agrega prueba: agrega un segundo código que la persona no pidió y un punto de
fallo más.

**3. Hash-only es el modo predeterminado.** Lo que no se recibe no se filtra. Con
declaraciones de salud dentro del documento, recibir el PDF convertiría a FNC en
encargado del tratamiento de datos de salud sin contrato que lo respalde.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from pscnc.models.motivos import RejectionReason

Sha256Hex = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class _Base(BaseModel):
    # `extra="forbid"`: un campo que el contrato no declara es un error del
    # integrador, y decírselo en la primera llamada es más barato que dejarlo
    # creer que ese campo hace algo.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ServiceLevel(StrEnum):
    """Los dos niveles del ADR-0007."""

    #: Acta de evidencia sellada. El documento no se modifica.
    SEALED_ACTA = "1"
    #: Lo del nivel 1 más firma PAdES con certificado efímero y sello de tiempo.
    PADES = "2"


class OtpMode(StrEnum):
    """Quién emite y verifica el código de un solo uso."""

    #: El tenant lo emitió y verificó; envía la prueba como evidencia.
    TENANT_VERIFIED = "TENANT_VERIFIED"
    #: FNC lo emite por el canal que el tenant indique.
    FNC_MANAGED = "FNC_MANAGED"


class OtpChannel(StrEnum):
    WHATSAPP = "WHATSAPP"
    SMS = "SMS"
    EMAIL = "EMAIL"


class TransactionStatus(StrEnum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


# --------------------------------------------------------------- Identidad ---
class IdentityDecision(_Base):
    """Decisión de identidad **ya tomada por el tenant**.

    FNC la asienta y no la revisa. El acta registra quién decidió, con qué umbral
    y con qué versión de política: así la responsabilidad queda trazada donde
    corresponde. FNC responde por la integridad del acta, no por la veracidad de
    lo que el tenant declaró.
    """

    approved: bool
    #: Umbral aplicado por el tenant, ya normalizado a 0-1.
    threshold_applied: float = Field(ge=0.0, le=1.0)
    #: Puntaje obtenido, normalizado a 0-1.
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    #: Escala original del puntaje. Un `98` sin escala declarada es
    #: indistinguible de un `0.98` mal convertido, y esa ambigüedad en un dato
    #: pericial es inaceptable.
    score_scale: Literal["0-1", "0-100"] = "0-1"
    model_version: str = Field(min_length=1, max_length=100)
    policy_version: str = Field(min_length=1, max_length=100)
    #: Referencia del proveedor de identidad del tenant, para trazar el origen.
    provider_reference: str = Field(min_length=1, max_length=200)
    liveness_verified: bool = False
    verified_at: datetime | None = None

    # El puntaje se acota a 0-1 por el propio campo (`le=1.0`): un `98` sin
    # normalizar se rechaza ahí. `score_scale` no cambia esa validación —registra
    # de qué escala viene el número—, porque un `0.98` y un `98` significan lo
    # mismo y solo la escala declarada permite reconstruirlo. Sin ella, la
    # evidencia pericial es un número sin unidad.


# --------------------------------------------------------------------- OTP ---
class OtpProof(_Base):
    """Evidencia de un OTP que **el tenant** ya emitió y verificó.

    Nunca lleva el código. Lo que viaja es su referencia opaca, el canal, el
    destino enmascarado y las marcas de tiempo: lo suficiente para acreditar el
    acto sin poder reproducirlo.
    """

    otp_reference: str = Field(min_length=1, max_length=200)
    channel: OtpChannel
    #: Destino enmascarado. Nunca el número o correo completo.
    destination_masked: str = Field(min_length=1, max_length=100)
    sent_at: datetime
    verified_at: datetime

    @model_validator(mode="after")
    def _verificado_despues_de_enviado(self) -> OtpProof:
        if self.verified_at < self.sent_at:
            raise ValueError("El OTP no puede verificarse antes de enviarse.")
        return self

    @model_validator(mode="after")
    def _destino_enmascarado(self) -> OtpProof:
        """Rechaza un destino que evidentemente no está enmascarado.

        No es una validación completa —no puede serlo— pero atrapa el error más
        frecuente: mandar el número entero por costumbre.
        """
        if "*" not in self.destination_masked and "…" not in self.destination_masked:
            raise ValueError(
                "El destino debe viajar enmascarado: no se conserva el número ni la "
                "dirección completa del firmante."
            )
        return self


# --------------------------------------------------------------- Documento ---
class DocumentRef(_Base):
    """El documento cerrado, identificado por su huella.

    En hash-only el contenido nunca llega a FNC. La versión viaja junto a la
    huella porque una huella suelta no dice contra qué comparar.
    """

    sha256: Sha256Hex
    version: int = Field(ge=1)
    code: str = Field(min_length=1, max_length=100)
    closed_at: datetime


# ------------------------------------------------------------- Peticiones ---
class CreateTransactionRequest(_Base):
    """Cuerpo de `POST /v1/transactions`."""

    #: Referencia del expediente en el sistema del tenant, que es el registro
    #: autoritativo del contrato (ADR-0009). Se citan mutuamente.
    tenant_reference: str = Field(min_length=1, max_length=200)
    document: DocumentRef
    identity_decision: IdentityDecision
    service_level: ServiceLevel = ServiceLevel.SEALED_ACTA
    otp_mode: OtpMode = OtpMode.TENANT_VERIFIED
    #: Jurisdicción del acto. Si se omite, la del despliegue.
    jurisdiction: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    #: Metadatos del tenant que se asientan tal cual. **No deben contener datos
    #: personales**: el acta puede entregarse y llegar a un juzgado.
    metadata: dict[str, str] = Field(default_factory=dict)


class ConfirmTransactionRequest(_Base):
    """Cuerpo de `POST /v1/transactions/{id}/confirm`."""

    #: Prueba del OTP verificado por el tenant. Obligatoria en `TENANT_VERIFIED`.
    otp_proof: OtpProof | None = None
    #: Código ingresado por el firmante. Solo en `FNC_MANAGED`. **Jamás se
    #: persiste ni se registra**: de él queda su hash (regla inviolable 1).
    otp_code: str | None = Field(default=None, min_length=4, max_length=10)
    #: Texto exacto que la persona aceptó, con su versión.
    consent_statement: str = Field(min_length=1, max_length=4000)
    consent_statement_version: str = Field(min_length=1, max_length=50)
    #: Huella del documento tal como se firmó. Debe coincidir con la registrada.
    document_sha256: Sha256Hex
    #: Contexto de red del firmante, con valor pericial.
    signer_ip: str | None = Field(default=None, max_length=45)
    signer_user_agent: str | None = Field(default=None, max_length=500)

    # --------------------------------------------------------- Solo nivel 2 --
    # Estos tres campos existen únicamente para el nivel 2, que sí necesita los
    # bytes para firmarlos. En el nivel 1 no se envían y el documento nunca llega
    # al servicio: es la diferencia que hace que hash-only sea el modo por
    # defecto (ADR-0009).

    #: PDF a firmar, en base64. Se procesa en memoria y **no se conserva** salvo
    #: que el tenant contrate custodia de forma explícita (ADR-0007).
    document_content: bytes | None = None
    #: Nombre del firmante para el `CN` del certificado efímero. Lo aporta el
    #: tenant, que es quien verificó la identidad.
    signer_common_name: str | None = Field(default=None, max_length=200)
    #: Número de documento para el `serialNumber`, con el formato que exige la
    #: jurisdicción.
    signer_national_id: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def _una_sola_via_de_otp(self) -> ConfirmTransactionRequest:
        """El OTP llega por una vía o por la otra, nunca por las dos.

        Recibir ambas dejaría sin definir cuál gobierna, y esa ambigüedad en el
        control que acredita la voluntad de firmar no es aceptable.
        """
        if self.otp_proof is not None and self.otp_code is not None:
            raise ValueError(
                "Envíe `otp_proof` (el tenant verificó) o `otp_code` (lo verifica FNC), "
                "nunca ambos."
            )
        return self


# -------------------------------------------------------------- Respuestas ---
class TransactionCreated(_Base):
    """Respuesta de `POST /v1/transactions`."""

    transaction_id: str
    tenant_reference: str
    status: TransactionStatus
    service_level: ServiceLevel
    jurisdiction: str
    document_sha256: Sha256Hex
    created_at: datetime
    expires_at: datetime


class ActaSeal(_Base):
    """Datos con los que un tercero verifica el acta."""

    jws: str
    payload_sha256: Sha256Hex
    key_alias: str
    algorithm: str = "ES256"
    #: Dónde obtener la clave pública. Se entrega para que el verificador no
    #: tenga que conocer de antemano la estructura del servicio.
    jwks_url: str = "/.well-known/fnc-keys.json"


class TransactionConfirmed(_Base):
    """Respuesta de `POST /v1/transactions/{id}/confirm`."""

    transaction_id: str
    tenant_reference: str
    status: TransactionStatus
    service_level: ServiceLevel
    confirmed_at: datetime
    acta: ActaSeal
    #: Código público de verificación, para `GET /v1/verify/{code}`.
    verification_code: str
    #: Presente solo en nivel 2.
    signed_document_sha256: Sha256Hex | None = None
    timestamp_authority: str | None = None


class Artifacts(_Base):
    """Respuesta de `GET /v1/transactions/{id}/artifacts`."""

    transaction_id: str
    status: TransactionStatus
    service_level: ServiceLevel
    acta: ActaSeal | None = None
    verification_code: str | None = None
    #: URL temporal del PDF firmado. Solo en nivel 2 y con custodia contratada.
    signed_document_url: str | None = None
    url_expires_in_seconds: int | None = None


class PublicVerification(_Base):
    """Respuesta de `GET /v1/verify/{code}`, pensada para una persona.

    Es pública y sin autenticación: la comprueba quien recibe el documento, que
    no tiene credenciales. Por eso **no lleva ningún dato personal**: confirma
    que el acto existe, sobre qué documento y bajo qué norma, sin revelar quién
    firmó a quien solo tiene el código.
    """

    verification_code: str
    exists: bool
    status: TransactionStatus | None = None
    document_sha256: Sha256Hex | None = None
    document_code: str | None = None
    signed_at: datetime | None = None
    jurisdiction: str | None = None
    #: Norma que da validez a la firma en esa jurisdicción.
    legal_basis: str | None = None
    service_level: ServiceLevel | None = None
    acta_jws: str | None = None


# ------------------------------------------------------------------ Error ---
class ErrorResponse(_Base):
    """Cuerpo de todo rechazo.

    El `motivo` es lo que el tenant debe programar; el `mensaje` es para que una
    persona entienda qué pasó y **puede cambiar entre versiones**.
    """

    motivo: RejectionReason
    mensaje: str
    transaction_id: str | None = None
    #: Detalle estructurado, dependiente del motivo.
    detalle: dict[str, str | int | list[str]] = Field(default_factory=dict)
    #: Si reintentar la misma operación puede tener sentido.
    reintentable: bool = False
