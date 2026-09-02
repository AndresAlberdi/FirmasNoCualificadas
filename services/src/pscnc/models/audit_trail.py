"""Modelo de la pista de auditoría forense (`PSCNC_Audit_Trail`).

Materializa el esquema descrito en `docs/diseno/esquema-base-datos-auditoria-pscnc.md`.
Cada objeto responde a una de las cuatro preguntas de una pericia informática:

* ``identity_evidence``      — ¿quién firmó?
* ``consent_evidence``       — ¿quiso firmar y tenía control exclusivo de sus medios?
* ``network_evidence``       — ¿desde dónde y con qué dispositivo?
* ``cryptographic_evidence`` — ¿qué se firmó y cuándo, con fecha cierta?

La validación es estricta a propósito: un registro incompleto es un registro que no
sirve como prueba, y es preferible fallar la transacción antes que persistir evidencia
inutilizable.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HexSha256 = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
UuidV4 = Annotated[
    str,
    Field(pattern=r"^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"),
]


class SigningStatus(StrEnum):
    """Estados de la máquina de estados de la sesión de firma."""

    INITIALIZED = "INITIALIZED"
    ONBOARDING_COMPLETED = "ONBOARDING_COMPLETED"
    SIGNING_COMPLETED = "SIGNING_COMPLETED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"
    COMPROMISED = "COMPROMISED"


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------- Identidad
class LivenessMeta(_Base):
    liveness_vendor: str
    liveness_confidence: float = Field(ge=0.0, le=1.0)
    spoof_check_passed: bool


class IdentityEvidence(_Base):
    """Vinculación unívoca de la firma con una persona física verificada."""

    document_type: Literal["CI_PY", "PASAPORTE"]
    national_id: str = Field(pattern=r"^[0-9]+$", min_length=4, max_length=15)
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    birth_date: date
    ocr_mrz_raw: str
    ocr_confidence: float = Field(ge=0.0, le=1.0)
    facial_match_score: float = Field(ge=0.0, le=1.0)
    liveness_detected: bool
    liveness_meta: LivenessMeta | None = None
    verification_partner_id: str
    aml_pep_checked: bool = False
    aml_pep_result: str | None = None

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def subject_serial_number(self) -> str:
        """Identificador del sujeto en el certificado X.509 (perfil DOC-ICPP-20)."""
        return f"PY-{self.national_id}"


# --------------------------------------------------------------------- Red
class Geolocation(_Base):
    country_code: str = Field(min_length=2, max_length=2)
    city: str | None = None
    latitude: float | None = Field(default=None, ge=-90.0, le=90.0)
    longitude: float | None = Field(default=None, ge=-180.0, le=180.0)
    isp: str | None = None


class NetworkEvidence(_Base):
    """Origen técnico de la conexión desde la que se produjo el acto de firma."""

    client_ip: str
    source_port: int = Field(ge=1, le=65535)
    user_agent: str
    tls_version: str
    tls_cipher: str
    geolocation: Geolocation | None = None


# ------------------------------------------------------------- Consentimiento
class OtpLog(_Base):
    channel_type: Literal["WHATSAPP", "SMS", "EMAIL"]
    destination: str
    otp_sent_timestamp: datetime
    otp_verified_timestamp: datetime
    provider_message_id: str
    otp_code_hash: HexSha256

    @model_validator(mode="after")
    def _verificar_orden_temporal(self) -> OtpLog:
        if self.otp_verified_timestamp < self.otp_sent_timestamp:
            raise ValueError(
                "El OTP no puede verificarse antes de haberse enviado: "
                "inconsistencia temporal en la evidencia de consentimiento."
            )
        return self


class ConsentEvidence(_Base):
    """Prueba del acto deliberado de voluntad y del control exclusivo de los medios."""

    explicit_consent_checked: Literal[True]
    consent_statement: str = Field(min_length=1)
    consent_statement_sha256: HexSha256 | None = None
    otp_channels: list[OtpLog] = Field(min_length=1)


# --------------------------------------------------------------- Criptografía
class TsaEvidence(_Base):
    """Sello de tiempo cualificado que otorga fecha cierta (RFC 3161)."""

    tsa_provider_name: str = Field(min_length=1)
    tsa_certificate_chain: list[str] = Field(min_length=1)
    rfc3161_response_base64: str = Field(min_length=1)
    timestamp_utc: datetime
    tsa_serial_number: str | None = None


class CryptographicEvidence(_Base):
    original_pdf_sha256: HexSha256
    signed_pdf_sha256: HexSha256
    user_certificate_serial: str
    user_certificate_pem: str | None = None
    ca_intermediate_serial: str
    signature_format: Literal["PAdES-B-T", "PAdES-B-LTA"] = "PAdES-B-T"
    signature_algorithm: str = "RSASSA_PKCS1_V1_5_SHA_256"
    digest_algorithm: str = "sha256"
    tsa_evidence: TsaEvidence

    @model_validator(mode="after")
    def _verificar_hashes_distintos(self) -> CryptographicEvidence:
        if self.original_pdf_sha256 == self.signed_pdf_sha256:
            raise ValueError(
                "El hash del documento firmado coincide con el del original: "
                "la firma no llegó a inyectarse en el PDF."
            )
        return self


# ---------------------------------------------------------------------- Ítem
class AuditTrailItem(_Base):
    """Registro completo de una sesión de firma, tal como se persiste en DynamoDB."""

    PK: str = Field(pattern=r"^TX#")
    SK: str = Field(pattern=r"^METADATA#V[0-9]+$")
    GSI1PK: str = Field(pattern=r"^CI#PY-[0-9]+$")
    GSI1SK: datetime
    GSI2PK: str = Field(pattern=r"^CLIENT#[a-zA-Z0-9_.-]+$")
    GSI2SK: datetime

    transaction_id: UuidV4
    b2b_client_id: str = Field(pattern=r"^[a-zA-Z0-9_.-]+$")
    status: SigningStatus
    created_at: datetime
    completed_at: datetime | None = None

    document_filename: str | None = None
    client_metadata: dict[str, str] = Field(default_factory=dict)

    identity_evidence: IdentityEvidence
    network_evidence: NetworkEvidence
    consent_evidence: ConsentEvidence | None = None
    cryptographic_evidence: CryptographicEvidence | None = None

    signed_document_key: str | None = None
    evidence_report_key: str | None = None

    @field_validator("PK")
    @classmethod
    def _validar_pk(cls, valor: str) -> str:
        if len(valor) != len("TX#") + 36:
            raise ValueError("PK debe tener la forma TX#{uuid v4}")
        return valor

    @model_validator(mode="after")
    def _verificar_coherencia_de_claves(self) -> AuditTrailItem:
        """Las claves derivadas deben coincidir con los atributos de negocio.

        Una divergencia entre PK y transaction_id haría irrecuperable la evidencia
        por los índices, de modo que se rechaza antes de persistir.
        """
        if f"TX#{self.transaction_id}" != self.PK:
            raise ValueError("PK inconsistente con transaction_id")
        if f"CI#{self.identity_evidence.subject_serial_number}" != self.GSI1PK:
            raise ValueError("GSI1PK inconsistente con la cédula del firmante")
        if f"CLIENT#{self.b2b_client_id}" != self.GSI2PK:
            raise ValueError("GSI2PK inconsistente con b2b_client_id")
        if self.status is SigningStatus.SIGNING_COMPLETED:
            if self.cryptographic_evidence is None:
                raise ValueError(
                    "Una sesión completada exige evidencia criptográfica: "
                    "no se admite un documento firmado sin pista de auditoría."
                )
            if self.consent_evidence is None:
                raise ValueError("Una sesión completada exige evidencia de consentimiento")
            if self.completed_at is None:
                raise ValueError("Una sesión completada exige completed_at")
        return self

    @classmethod
    def build_keys(
        cls,
        *,
        transaction_id: str,
        national_id: str,
        b2b_client_id: str,
        created_at: datetime,
        version: int = 1,
    ) -> dict[str, object]:
        """Construye las claves primarias y de índice de forma centralizada."""
        return {
            "PK": f"TX#{transaction_id}",
            "SK": f"METADATA#V{version}",
            "GSI1PK": f"CI#PY-{national_id}",
            "GSI1SK": created_at,
            "GSI2PK": f"CLIENT#{b2b_client_id}",
            "GSI2SK": created_at,
        }
