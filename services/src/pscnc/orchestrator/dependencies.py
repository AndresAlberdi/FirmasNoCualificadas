"""Composición de dependencias del servicio.

Un único punto donde se decide qué implementación se usa según el entorno. Fuera
de este módulo, el código depende de contratos y no de proveedores concretos.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from jurisdictions import require_profile
from pscnc.compliance.legal_guard import LegalGuard
from pscnc.config import Settings, get_settings
from pscnc.crypto.ca_signer import CaSigner, KmsCaSigner, LocalCaSigner
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority
from pscnc.crypto.pades import PadesSigner, build_timestamper_factory
from pscnc.logging_setup import get_logger
from pscnc.onboarding.client import (
    HttpOnboardingClient,
    OnboardingClient,
    SandboxOnboardingClient,
)
from pscnc.orchestrator.security import SecretResolver, SecretsManagerResolver, StaticSecretResolver
from pscnc.orchestrator.state_machine import SigningService
from pscnc.repositories.dynamo_audit import AuditTrailRepository
from pscnc.repositories.s3_vault import DocumentVault

logger = get_logger(__name__)


def _cargar_certificado_ca(settings: Settings) -> bytes:
    """Carga el certificado de la CA intermedia en formato DER."""
    ruta = Path(settings.ca_cert_path)
    if not ruta.exists():
        raise RuntimeError(
            f"No se encuentra el certificado de la CA intermedia en {ruta}. "
            "Configure PSCNC_CA_CERT_PATH con el certificado emitido para la clave de KMS."
        )
    contenido = ruta.read_bytes()
    if contenido.lstrip().startswith(b"-----BEGIN"):
        import base64

        cuerpo = b"".join(
            linea for linea in contenido.splitlines() if not linea.startswith(b"-----")
        )
        return base64.b64decode(cuerpo)
    return contenido


def build_ca_signer(settings: Settings) -> CaSigner:
    if settings.crypto_backend == "kms":
        return KmsCaSigner(
            settings.kms_ca_key_id,
            region=settings.aws_region,
            signing_algorithm=settings.kms_signing_algorithm,
        )
    logger.warning("using_local_ca_signer", environment=settings.environment)
    return LocalCaSigner(settings.local_ca_key_path)


def build_onboarding_client(settings: Settings) -> OnboardingClient:
    if settings.environment == "sandbox" or not settings.onboarding_base_url:
        logger.warning("using_sandbox_onboarding_client", environment=settings.environment)
        return SandboxOnboardingClient()
    return HttpOnboardingClient(settings.onboarding_base_url, api_key=settings.onboarding_api_key)


def build_secret_resolver(settings: Settings) -> SecretResolver:
    if settings.hmac_secret_arn:
        return SecretsManagerResolver(settings.hmac_secret_arn, region=settings.aws_region)
    logger.warning("using_static_secret_resolver", environment=settings.environment)
    return StaticSecretResolver(secrets={"sandbox-client": b"sandbox-secret"})


@lru_cache(maxsize=1)
def build_signing_service() -> SigningService:
    """Construye el servicio de firma con todas sus dependencias resueltas."""
    settings = get_settings()
    settings.require_signing_configuration()

    ca = EphemeralCertificateAuthority(
        ca_certificate_der=_cargar_certificado_ca(settings),
        ca_signer=build_ca_signer(settings),
        crl_url=settings.crl_distribution_url,
        policy_oid=settings.cert_policy_oid,
        backdate_minutes=settings.ephemeral_cert_backdate_minutes,
        validity_minutes=settings.ephemeral_cert_validity_minutes,
    )

    signer = PadesSigner(
        certificate_authority=ca,
        timestamper_factory=build_timestamper_factory(
            url=settings.tsa_url,
            provider_name=settings.tsa_provider_name,
            username=settings.tsa_username,
            password=settings.tsa_password,
            timeout=settings.tsa_timeout_seconds,
            max_retries=settings.tsa_max_retries,
        ),
        jurisdiction=require_profile(settings.jurisdiction, environment=settings.environment),
    )

    return SigningService(
        repository=AuditTrailRepository(settings.audit_table, region=settings.aws_region),
        vault=DocumentVault(
            signed_bucket=settings.signed_bucket,
            evidence_bucket=settings.evidence_bucket,
            region=settings.aws_region,
            presigned_ttl=settings.presigned_url_ttl,
        ),
        onboarding=build_onboarding_client(settings),
        certificate_authority=ca,
        signer=signer,
        legal_guard=LegalGuard.for_jurisdiction(settings.jurisdiction),
        min_facial_match_score=settings.min_facial_match_score,
        session_ttl_minutes=settings.session_ttl_minutes,
        presigned_ttl=settings.presigned_url_ttl,
        jurisdiction=settings.jurisdiction,
    )


@lru_cache(maxsize=1)
def get_secret_resolver() -> SecretResolver:
    return build_secret_resolver(get_settings())
