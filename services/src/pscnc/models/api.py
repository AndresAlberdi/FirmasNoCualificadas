"""Contratos de la API B2B (`/v1/signing-sessions`)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from pscnc.models.audit_trail import SigningStatus


class _Base(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SigningSessionCreated(_Base):
    """Respuesta de `POST /v1/signing-sessions`."""

    signing_session_id: str
    status: SigningStatus
    original_document_hash: str
    created_at: datetime
    expires_at: datetime


class ConfirmSignatureRequest(_Base):
    """Cuerpo de `POST /v1/signing-sessions/{id}/confirm`.

    El código OTP se recibe para su verificación pero nunca se persiste ni se
    registra: en la evidencia solo queda su hash SHA-256.
    """

    consent_otp_code: str = Field(min_length=4, max_length=10, pattern=r"^[0-9]+$")
    consent_statement: str = Field(min_length=1, max_length=4000)
    visual_signature_enabled: bool = True
    signature_page: int = Field(default=1, ge=1)
    signature_coordinate_x: float = Field(default=100.0, ge=0.0)
    signature_coordinate_y: float = Field(default=150.0, ge=0.0)
    signature_width: float = Field(default=180.0, gt=0.0)
    signature_height: float = Field(default=60.0, gt=0.0)


class TimestampInfo(_Base):
    authority: str
    serial: str | None = None
    time: datetime


class SigningSessionCompleted(_Base):
    """Respuesta de la confirmación de firma."""

    signing_session_id: str
    status: SigningStatus
    signed_document_hash: str
    user_certificate_serial: str
    signature_format: str
    timestamp: TimestampInfo


class VerificationSummary(_Base):
    aml_pep_checked: bool
    biometric_score: float
    liveness_detected: bool
    identity_match_approved: bool


class EvidenceBundle(_Base):
    """Respuesta de `GET /v1/signing-sessions/{id}/evidence`.

    Las URLs son pre-firmadas de S3 con vigencia limitada (300 s por defecto).
    """

    signing_session_id: str
    status: SigningStatus
    signed_document_url: str | None = None
    evidence_report_url: str | None = None
    url_expires_in_seconds: int
    original_document_hash: str
    signed_document_hash: str | None = None
    verifications: VerificationSummary


class HealthResponse(_Base):
    status: str
    environment: str
    version: str
    crypto_backend: str
