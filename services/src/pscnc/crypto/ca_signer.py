"""Firmantes de la Autoridad de Certificación intermedia.

La clave privada de la CA nunca se materializa en el proceso: el módulo expone
una operación única —firmar un digest de 32 bytes— y la implementación de
producción la delega en ``kms:Sign``.

El backend ``local`` existe exclusivamente para desarrollo y pruebas y está
prohibido en ``staging`` y ``prod`` por validación de configuración.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol, runtime_checkable

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from pscnc.errors import SigningError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

# Correspondencia entre el algoritmo de KMS y el nombre ASN.1 del algoritmo de firma.
ALGORITMOS_SOPORTADOS: dict[str, str] = {
    "RSASSA_PKCS1_V1_5_SHA_256": "sha256_rsa",
    "RSASSA_PSS_SHA_256": "rsassa_pss",
}


@runtime_checkable
class CaSigner(Protocol):
    """Contrato mínimo de un firmante de CA."""

    @property
    def signing_algorithm(self) -> str:
        """Identificador del algoritmo de firma (nomenclatura de AWS KMS)."""

    def sign_digest(self, digest: bytes) -> bytes:
        """Firma un digest SHA-256 de 32 bytes y devuelve la firma en crudo."""

    def public_key_der(self) -> bytes:
        """Devuelve el ``SubjectPublicKeyInfo`` DER de la clave pública de la CA."""


class KmsCaSigner:
    """Firmante respaldado por AWS KMS (HSM FIPS 140-2 Nivel 3).

    Se envía el digest, nunca el mensaje completo: además de ser el modo correcto
    para datos de tamaño arbitrario, evita transmitir el contenido a firmar.
    """

    def __init__(
        self,
        key_id: str,
        *,
        region: str,
        signing_algorithm: str = "RSASSA_PKCS1_V1_5_SHA_256",
        client: object | None = None,
    ) -> None:
        if signing_algorithm not in ALGORITMOS_SOPORTADOS:
            raise SigningError(f"Algoritmo de firma no permitido por la DPSC: {signing_algorithm}")
        self._key_id = key_id
        self._signing_algorithm = signing_algorithm
        self._client = client or boto3.client(
            "kms",
            region_name=region,
            config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
        )
        self._public_key_cache: bytes | None = None

    @property
    def signing_algorithm(self) -> str:
        return self._signing_algorithm

    def sign_digest(self, digest: bytes) -> bytes:
        if len(digest) != 32:
            raise SigningError("Se esperaba un digest SHA-256 de 32 bytes")
        try:
            respuesta = self._client.sign(  # type: ignore[attr-defined]
                KeyId=self._key_id,
                Message=digest,
                MessageType="DIGEST",
                SigningAlgorithm=self._signing_algorithm,
            )
        except (ClientError, BotoCoreError) as exc:
            logger.error("kms_sign_failed", key_id=self._key_id, error=str(exc))
            raise SigningError("La operación de firma en AWS KMS falló") from exc
        return bytes(respuesta["Signature"])

    def public_key_der(self) -> bytes:
        if self._public_key_cache is None:
            try:
                respuesta = self._client.get_public_key(KeyId=self._key_id)  # type: ignore[attr-defined]
            except (ClientError, BotoCoreError) as exc:
                raise SigningError("No se pudo obtener la clave pública de la CA") from exc
            self._public_key_cache = bytes(respuesta["PublicKey"])
        return self._public_key_cache


class LocalCaSigner:
    """Firmante de desarrollo con la clave de la CA en un archivo PEM.

    ADVERTENCIA: no utilizar fuera de desarrollo. La configuración impide
    activarlo en ``staging`` y ``prod``.
    """

    def __init__(self, key_path: str | Path, *, password: bytes | None = None) -> None:
        from cryptography.hazmat.primitives import serialization

        ruta = Path(key_path)
        if not ruta.exists():
            raise SigningError(f"No existe la clave local de la CA: {ruta}")
        self._private_key = serialization.load_pem_private_key(ruta.read_bytes(), password=password)
        logger.warning("local_ca_signer_enabled", path=str(ruta))

    @property
    def signing_algorithm(self) -> str:
        return "RSASSA_PKCS1_V1_5_SHA_256"

    def sign_digest(self, digest: bytes) -> bytes:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives.asymmetric import utils as asym_utils

        if not isinstance(self._private_key, rsa.RSAPrivateKey):
            raise SigningError("La clave local de la CA debe ser RSA")
        # El mensaje ya viene digerido: se firma el digest tal cual (Prehashed).
        return self._private_key.sign(
            digest,
            padding.PKCS1v15(),
            asym_utils.Prehashed(hashes.SHA256()),
        )

    def public_key_der(self) -> bytes:
        from cryptography.hazmat.primitives import serialization

        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


def sha256_digest(data: bytes) -> bytes:
    """Digest SHA-256 de un bloque de bytes."""
    return hashlib.sha256(data).digest()
