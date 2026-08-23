"""Almacenamiento de documentos firmados y de expedientes de evidencia.

El expediente se escribe en un bucket con Object Lock en modo COMPLIANCE: una vez
escrito no puede modificarse ni eliminarse hasta el vencimiento de la retención,
ni siquiera por el usuario raíz de la cuenta. Ese es el fundamento técnico del
valor probatorio (ADR-0003).

Las descargas nunca se sirven desde el backend: se emiten URLs pre-firmadas de
vigencia corta para que el binario viaje directamente desde S3 al cliente.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from pscnc.errors import EvidencePersistenceError
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class StoredObject:
    bucket: str
    key: str
    sha256: str


class DocumentVault:
    """Escritura de documentos y emisión de URLs pre-firmadas."""

    def __init__(
        self,
        *,
        signed_bucket: str,
        evidence_bucket: str,
        region: str,
        kms_key_id: str | None = None,
        presigned_ttl: int = 300,
        client: Any | None = None,
    ) -> None:
        self._signed_bucket = signed_bucket
        self._evidence_bucket = evidence_bucket
        self._kms_key_id = kms_key_id
        self._ttl = presigned_ttl
        self._client = client or boto3.client(
            "s3",
            region_name=region,
            config=BotoConfig(
                signature_version="s3v4",
                retries={"max_attempts": 5, "mode": "standard"},
            ),
        )

    # ------------------------------------------------------------- Claves ----
    @staticmethod
    def signed_key(b2b_client_id: str, transaction_id: str) -> str:
        """Prefijo por inquilino: refuerza el aislamiento también en el almacenamiento."""
        return f"{b2b_client_id}/{transaction_id}/documento-firmado.pdf"

    @staticmethod
    def evidence_key(b2b_client_id: str, transaction_id: str) -> str:
        return f"{b2b_client_id}/{transaction_id}/expediente-evidencias.pdf"

    @staticmethod
    def original_key(b2b_client_id: str, transaction_id: str) -> str:
        """El original se conserva junto al firmado: es la base de la comparación pericial."""
        return f"{b2b_client_id}/{transaction_id}/documento-original.pdf"

    # ---------------------------------------------------------- Escritura ----
    def put_signed_document(
        self, *, b2b_client_id: str, transaction_id: str, content: bytes, sha256: str
    ) -> StoredObject:
        clave = self.signed_key(b2b_client_id, transaction_id)
        self._put(self._signed_bucket, clave, content, sha256, transaction_id)
        return StoredObject(bucket=self._signed_bucket, key=clave, sha256=sha256)

    def put_original_document(
        self, *, b2b_client_id: str, transaction_id: str, content: bytes, sha256: str
    ) -> StoredObject:
        clave = self.original_key(b2b_client_id, transaction_id)
        self._put(self._signed_bucket, clave, content, sha256, transaction_id)
        return StoredObject(bucket=self._signed_bucket, key=clave, sha256=sha256)

    def get_original_document(self, *, b2b_client_id: str, transaction_id: str) -> bytes:
        """Recupera el documento original cargado al iniciar la sesión."""
        clave = self.original_key(b2b_client_id, transaction_id)
        try:
            respuesta = self._client.get_object(Bucket=self._signed_bucket, Key=clave)
            return bytes(respuesta["Body"].read())
        except ClientError as exc:
            logger.error("s3_get_failed", key=clave, error=str(exc))
            raise EvidencePersistenceError(
                "No se pudo recuperar el documento original de la sesión"
            ) from exc

    def put_evidence_report(
        self, *, b2b_client_id: str, transaction_id: str, content: bytes, sha256: str
    ) -> StoredObject:
        clave = self.evidence_key(b2b_client_id, transaction_id)
        self._put(self._evidence_bucket, clave, content, sha256, transaction_id)
        return StoredObject(bucket=self._evidence_bucket, key=clave, sha256=sha256)

    def _put(self, bucket: str, key: str, content: bytes, sha256: str, transaction_id: str) -> None:
        parametros: dict[str, Any] = {
            "Bucket": bucket,
            "Key": key,
            "Body": content,
            "ContentType": "application/pdf",
            "ServerSideEncryption": "aws:kms",
            # Metadatos de integridad: permiten verificar el objeto sin descargarlo entero.
            "Metadata": {"sha256": sha256, "transaction-id": transaction_id},
        }
        if self._kms_key_id:
            parametros["SSEKMSKeyId"] = self._kms_key_id

        try:
            self._client.put_object(**parametros)
        except ClientError as exc:
            logger.error("s3_put_failed", bucket=bucket, key=key, error=str(exc))
            raise EvidencePersistenceError(
                "No se pudo almacenar el documento en la bóveda"
            ) from exc

        logger.info("s3_object_stored", bucket=bucket, key=key, sha256=sha256, bytes=len(content))

    # ----------------------------------------------------------- Descarga ----
    def presigned_url(self, bucket: str, key: str, *, ttl: int | None = None) -> str:
        """Genera una URL de descarga temporal (300 s por defecto)."""
        try:
            return str(
                self._client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=ttl or self._ttl,
                )
            )
        except ClientError as exc:
            raise EvidencePersistenceError("No se pudo generar la URL de descarga") from exc

    def presigned_signed_document(self, b2b_client_id: str, transaction_id: str) -> str:
        return self.presigned_url(
            self._signed_bucket, self.signed_key(b2b_client_id, transaction_id)
        )

    def presigned_evidence_report(self, b2b_client_id: str, transaction_id: str) -> str:
        return self.presigned_url(
            self._evidence_bucket, self.evidence_key(b2b_client_id, transaction_id)
        )
