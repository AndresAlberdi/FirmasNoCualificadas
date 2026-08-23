"""Jerarquía de errores del dominio.

Cada error define el código HTTP y un identificador estable que el cliente B2B
puede tratar programáticamente. Los mensajes nunca contienen datos personales.
"""

from __future__ import annotations


class PscncError(Exception):
    """Error base del dominio."""

    http_status: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, *, detail: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}

    def to_payload(self) -> dict[str, object]:
        return {"error": {"code": self.code, "message": self.message, **self.detail}}


# --------------------------------------------------------------- Autenticación
class AuthenticationError(PscncError):
    http_status = 401
    code = "unauthenticated"


class TenantMismatchError(PscncError):
    """Intento de acceso a datos de otro inquilino (ADR-0005)."""

    http_status = 403
    code = "tenant_mismatch"


# ------------------------------------------------------------------ Onboarding
class OnboardingNotApprovedError(PscncError):
    http_status = 409
    code = "onboarding_not_approved"


class BiometricThresholdError(PscncError):
    http_status = 409
    code = "biometric_threshold_not_met"


class OnboardingUnavailableError(PscncError):
    http_status = 503
    code = "onboarding_unavailable"


# ------------------------------------------------------------------ Legalidad
class LegallyExcludedDocumentError(PscncError):
    """El acto jurídico está excluido de la firma electrónica no cualificada."""

    http_status = 403
    code = "legally_excluded_document"


# ---------------------------------------------------------------- Transacción
class SigningSessionNotFoundError(PscncError):
    http_status = 404
    code = "signing_session_not_found"


class InvalidSessionStateError(PscncError):
    http_status = 409
    code = "invalid_session_state"


class SessionExpiredError(PscncError):
    http_status = 410
    code = "signing_session_expired"


class ConsentVerificationError(PscncError):
    http_status = 401
    code = "consent_verification_failed"


# --------------------------------------------------------------- Criptografía
class SigningError(PscncError):
    http_status = 502
    code = "signing_failed"


class TimestampError(PscncError):
    """Fallo del sellado de tiempo cualificado.

    Sin fecha cierta la firma pierde su valor probatorio diferencial: la
    transacción falla completa en lugar de degradarse a PAdES-B-B.
    """

    http_status = 502
    code = "timestamp_authority_unavailable"


class DocumentIntegrityError(PscncError):
    http_status = 422
    code = "document_integrity_error"


class EvidencePersistenceError(PscncError):
    """No se pudo persistir la evidencia: el documento firmado no se entrega."""

    http_status = 500
    code = "evidence_persistence_failed"
