"""Configuración del servicio, cargada desde variables de entorno.

Toda la configuración es explícita y validada al arranque: un servicio que firma
documentos con valor jurídico no debe iniciar con parámetros ambiguos.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from jurisdictions import DEFAULT_JURISDICTION

CryptoBackend = Literal["kms", "local"]
Environment = Literal["sandbox", "dev", "staging", "prod"]


class Settings(BaseSettings):
    """Parámetros operativos del PSCNC."""

    model_config = SettingsConfigDict(
        env_prefix="PSCNC_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Environment = "dev"
    crypto_backend: CryptoBackend = "local"

    # Jurisdicción por defecto del despliegue. Cada tenant puede declarar la suya;
    # esta es la que rige cuando no lo hace. De ella salen la norma citada, el
    # formato del documento de identidad, el plazo de conservación y la lista de
    # actos excluidos (ADR-0008).
    jurisdiction: str = DEFAULT_JURISDICTION

    # Inquilinos con claves propias en este despliegue. De acá sale el documento
    # de claves públicas: un inquilino que no figure no puede sellar actas ni ver
    # su clave publicada, de modo que la lista es también un control de alta.
    tenant_ids: list[str] = Field(default_factory=list)

    # --- AWS -----------------------------------------------------------------
    aws_region: str = Field(default="us-east-1", alias="AWS_REGION")
    kms_ca_key_id: str = ""
    kms_signing_algorithm: str = "RSASSA_PKCS1_V1_5_SHA_256"
    audit_table: str = "PSCNC_Audit_Trail"
    # Tabla propia, separada de la de auditoría: aquella no puede expirar y
    # esta sí (T-11). Vacía en desarrollo, donde se usa el almacén en memoria.
    idempotency_table: str = ""
    signed_bucket: str = ""
    evidence_bucket: str = ""
    presigned_url_ttl: int = Field(default=300, ge=60, le=900)

    # --- Identidad de la CA intermedia --------------------------------------
    ca_common_name: str = "CA Intermedia FENC"
    ca_organization: str = "PSCNC"
    ca_organization_identifier: str = ""
    ca_cert_path: str = ""
    crl_distribution_url: str = ""
    cert_policy_oid: str = ""

    ephemeral_cert_backdate_minutes: int = Field(default=5, ge=0, le=60)
    ephemeral_cert_validity_minutes: int = Field(default=15, ge=5, le=120)

    # --- Autoridad de Sellado de Tiempo --------------------------------------
    tsa_url: str = ""
    tsa_provider_name: str = ""
    tsa_username: str = ""
    tsa_password: str = ""
    tsa_timeout_seconds: int = Field(default=10, ge=1, le=60)
    tsa_max_retries: int = Field(default=3, ge=1, le=5)

    # --- Onboarding ----------------------------------------------------------
    onboarding_base_url: str = ""
    onboarding_api_key: str = ""
    min_facial_match_score: float = Field(default=0.95, ge=0.0, le=1.0)

    # --- Seguridad de la API B2B ---------------------------------------------
    hmac_secret_arn: str = ""
    hmac_max_skew_seconds: int = Field(default=300, ge=30, le=900)
    session_ttl_minutes: int = Field(default=60, ge=5, le=1440)

    # --- Solo desarrollo -----------------------------------------------------
    local_ca_key_path: str = ""
    local_ca_cert_path: str = ""

    @field_validator("crypto_backend")
    @classmethod
    def _forbid_local_backend_outside_dev(cls, value: CryptoBackend, info: object) -> CryptoBackend:
        """El backend de archivo jamás puede activarse en entornos reales."""
        data = getattr(info, "data", {}) or {}
        environment = data.get("environment", "dev")
        if value == "local" and environment in ("staging", "prod"):
            raise ValueError(
                "PSCNC_CRYPTO_BACKEND='local' está prohibido en staging y prod: "
                "la clave de la CA debe residir en AWS KMS."
            )
        return value

    @field_validator("jurisdiction")
    @classmethod
    def _validar_jurisdiccion(cls, value: str, info: object) -> str:
        """Falla al arranque si la jurisdicción no existe o no puede operar.

        Un perfil sin validación legal sirve para probar que la arquitectura
        generaliza; firmar con él produciría una constancia que cita una norma que
        nadie verificó.
        """
        from jurisdictions import require_profile

        data = getattr(info, "data", {}) or {}
        require_profile(value, environment=data.get("environment", "dev"))
        return value.upper()

    @property
    def is_production(self) -> bool:
        return self.environment == "prod"

    def require_signing_configuration(self) -> None:
        """Verifica que estén presentes los parámetros sin los cuales no se puede firmar.

        Se invoca al arranque para fallar de forma temprana y ruidosa en lugar de
        producir una firma incompleta en tiempo de ejecución.
        """
        faltantes: list[str] = []

        if self.crypto_backend == "kms" and not self.kms_ca_key_id:
            faltantes.append("PSCNC_KMS_CA_KEY_ID")
        if not self.tsa_url:
            faltantes.append("PSCNC_TSA_URL")
        if not self.tsa_provider_name:
            faltantes.append("PSCNC_TSA_PROVIDER_NAME")
        if not self.crl_distribution_url:
            faltantes.append("PSCNC_CRL_DISTRIBUTION_URL")
        if self.environment != "sandbox":
            if not self.signed_bucket:
                faltantes.append("PSCNC_SIGNED_BUCKET")
            if not self.evidence_bucket:
                faltantes.append("PSCNC_EVIDENCE_BUCKET")

        if faltantes:
            raise RuntimeError(
                "Configuración incompleta para operar el motor de firma. "
                f"Variables faltantes: {', '.join(faltantes)}"
            )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Devuelve la configuración del proceso (memorizada)."""
    return Settings()
