"""Cliente del módulo de Onboarding existente.

Este servicio no verifica identidad: la consume. El contrato con el módulo de
onboarding es deliberadamente estrecho —resolver un token y verificar un OTP—
para que un cambio en aquel sistema no se propague al motor de firma.

Si el onboarding no está disponible, la sesión de firma **no se crea**: es
preferible rechazar la operación que firmar sin identidad acreditada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import requests

from pscnc.errors import (
    ConsentVerificationError,
    OnboardingNotApprovedError,
    OnboardingUnavailableError,
)
from pscnc.logging_setup import get_logger
from pscnc.models.audit_trail import IdentityEvidence, OtpLog

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class OnboardingSnapshot:
    """Fotografía del onboarding aprobado en el instante de iniciar la firma."""

    onboarding_id: str
    approved: bool
    identity: IdentityEvidence
    contact_phone_e164: str | None = None
    contact_email: str | None = None


class OnboardingClient(Protocol):
    def fetch(self, onboarding_token: str) -> OnboardingSnapshot: ...

    def verify_otp(self, onboarding_token: str, code: str) -> OtpLog: ...


class HttpOnboardingClient:
    """Implementación HTTP contra el módulo de onboarding corporativo."""

    def __init__(self, base_url: str, *, api_key: str, timeout: int = 10) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        )

    def fetch(self, onboarding_token: str) -> OnboardingSnapshot:
        datos = self._get(f"/v1/onboardings/{onboarding_token}")

        estado = str(datos.get("status", "")).upper()
        if estado != "APPROVED":
            logger.warning("onboarding_not_approved", status=estado)
            raise OnboardingNotApprovedError("El onboarding referenciado no se encuentra aprobado.")

        return OnboardingSnapshot(
            onboarding_id=str(datos["onboarding_id"]),
            approved=True,
            identity=IdentityEvidence.model_validate(datos["identity"]),
            contact_phone_e164=datos.get("contact_phone_e164"),
            contact_email=datos.get("contact_email"),
        )

    def verify_otp(self, onboarding_token: str, code: str) -> OtpLog:
        """Delega la verificación del OTP; el código nunca se almacena ni se registra."""
        try:
            respuesta = self._session.post(
                f"{self._base_url}/v1/onboardings/{onboarding_token}/otp/verify",
                json={"code": code},
                timeout=self._timeout,
            )
        except requests.RequestException as exc:
            raise OnboardingUnavailableError("El módulo de onboarding no responde") from exc

        if respuesta.status_code in (400, 401, 409):
            raise ConsentVerificationError("El código de consentimiento es inválido o expiró")
        if respuesta.status_code >= 500:
            raise OnboardingUnavailableError("El módulo de onboarding devolvió un error")

        return OtpLog.model_validate(respuesta.json())

    def _get(self, path: str) -> dict[str, Any]:
        try:
            respuesta = self._session.get(f"{self._base_url}{path}", timeout=self._timeout)
        except requests.RequestException as exc:
            raise OnboardingUnavailableError("El módulo de onboarding no responde") from exc

        if respuesta.status_code == 404:
            raise OnboardingNotApprovedError("El token de onboarding no existe")
        if respuesta.status_code >= 500:
            raise OnboardingUnavailableError("El módulo de onboarding devolvió un error")
        return dict(respuesta.json())


class SandboxOnboardingClient:
    """Onboarding simulado para el entorno `sandbox` y las pruebas automatizadas.

    Genera datos sintéticos: nunca debe habilitarse con tráfico real.
    """

    OTP_ACEPTADO = "000000"

    def __init__(self, *, national_id: str = "4829153") -> None:
        self._national_id = national_id

    def fetch(self, onboarding_token: str) -> OnboardingSnapshot:
        return OnboardingSnapshot(
            onboarding_id=onboarding_token,
            approved=True,
            identity=IdentityEvidence(
                document_type="CI_PY",
                national_id=self._national_id,
                first_name="Firmante",
                last_name="De Prueba",
                birth_date="1985-03-14",
                ocr_mrz_raw="IDPRY4829153<<<<<<<<<<<<<<<<8503140M3001019PRY<<<<<<<<<<<8",
                ocr_confidence=0.99,
                facial_match_score=0.985,
                liveness_detected=True,
                verification_partner_id="sandbox-provider",
                aml_pep_checked=True,
                aml_pep_result="SIN COINCIDENCIAS",
            ),
            contact_phone_e164="+595981000000",
            contact_email="sandbox@example.com.py",
        )

    def verify_otp(self, onboarding_token: str, code: str) -> OtpLog:
        import hashlib

        if code != self.OTP_ACEPTADO:
            raise ConsentVerificationError("Código de consentimiento inválido en modo sandbox")

        ahora = datetime.now(UTC)
        return OtpLog(
            channel_type="WHATSAPP",
            destination="+595981000000",
            otp_sent_timestamp=ahora,
            otp_verified_timestamp=ahora,
            provider_message_id=f"sandbox-{onboarding_token}",
            otp_code_hash=hashlib.sha256(code.encode()).hexdigest(),
        )
