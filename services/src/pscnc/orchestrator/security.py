"""Autenticación de clientes B2B mediante firma HMAC-SHA256 de la petición.

Cadena canónica firmada::

    {MÉTODO}\\n{ruta}\\n{timestamp ISO-8601}\\n{sha256_hex(cuerpo)}

Cabeceras requeridas:

* ``X-PSCNC-Client``    — identificador del cliente B2B.
* ``X-PSCNC-Timestamp`` — instante de la petición en ISO-8601 UTC.
* ``X-PSCNC-Signature`` — HMAC-SHA256 hexadecimal de la cadena canónica.

Propiedades del diseño:

* El ``b2b_client_id`` proviene de la credencial verificada y **nunca** del
  cuerpo de la petición (ADR-0005).
* La ventana temporal acotada limita la reutilización de una petición capturada.
* La comparación de firmas es en tiempo constante.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from pscnc.errors import AuthenticationError
from pscnc.logging_setup import get_logger
from pscnc.repositories.dynamo_audit import SecurityContext

logger = get_logger(__name__)

HEADER_CLIENT = "x-pscnc-client"
HEADER_TIMESTAMP = "x-pscnc-timestamp"
HEADER_SIGNATURE = "x-pscnc-signature"


class SecretResolver(Protocol):
    """Resuelve el secreto HMAC de un cliente B2B."""

    def secret_for(self, b2b_client_id: str) -> bytes: ...


@dataclass(slots=True)
class StaticSecretResolver:
    """Resolución en memoria. Para desarrollo y pruebas."""

    secrets: dict[str, bytes]

    def secret_for(self, b2b_client_id: str) -> bytes:
        secreto = self.secrets.get(b2b_client_id)
        if secreto is None:
            raise AuthenticationError("Credenciales inválidas")
        return secreto


class SecretsManagerResolver:
    """Resolución contra AWS Secrets Manager con caché en memoria.

    El secreto se almacena como un objeto JSON ``{"cliente": "secreto"}`` en un
    único secreto rotado automáticamente cada 90 días.
    """

    def __init__(self, secret_arn: str, *, region: str, client: object | None = None) -> None:
        import boto3

        self._secret_arn = secret_arn
        self._client = client or boto3.client("secretsmanager", region_name=region)
        self._cache: dict[str, bytes] = {}
        self._cache_expira: datetime = datetime.min.replace(tzinfo=UTC)

    def secret_for(self, b2b_client_id: str) -> bytes:
        ahora = datetime.now(UTC)
        if ahora >= self._cache_expira:
            self._refrescar(ahora)
        secreto = self._cache.get(b2b_client_id)
        if secreto is None:
            raise AuthenticationError("Credenciales inválidas")
        return secreto

    def _refrescar(self, ahora: datetime) -> None:
        import json

        try:
            respuesta = self._client.get_secret_value(SecretId=self._secret_arn)  # type: ignore[attr-defined]
            datos = json.loads(respuesta["SecretString"])
        except Exception as exc:
            logger.error("secret_refresh_failed", error=str(exc))
            raise AuthenticationError("No se pudieron resolver las credenciales") from exc

        self._cache = {k: str(v).encode("utf-8") for k, v in datos.items()}
        self._cache_expira = ahora + timedelta(minutes=5)


def canonical_string(method: str, path: str, timestamp: str, body: bytes) -> str:
    """Construye la cadena canónica que el cliente debe firmar."""
    return f"{method.upper()}\n{path}\n{timestamp}\n{hashlib.sha256(body).hexdigest()}"


def sign_request(secret: bytes, method: str, path: str, timestamp: str, body: bytes) -> str:
    """Calcula la firma de una petición. Se expone para el SDK de clientes y las pruebas."""
    canonica = canonical_string(method, path, timestamp, body)
    return hmac.new(secret, canonica.encode("utf-8"), hashlib.sha256).hexdigest()


def authenticate(
    *,
    headers: dict[str, str],
    method: str,
    path: str,
    body: bytes,
    resolver: SecretResolver,
    max_skew_seconds: int = 300,
    now: datetime | None = None,
) -> SecurityContext:
    """Verifica la firma de la petición y devuelve el contexto del inquilino."""
    normalizadas = {k.lower(): v for k, v in headers.items()}
    cliente = normalizadas.get(HEADER_CLIENT)
    timestamp = normalizadas.get(HEADER_TIMESTAMP)
    firma = normalizadas.get(HEADER_SIGNATURE)

    if not cliente or not timestamp or not firma:
        raise AuthenticationError("Faltan cabeceras de autenticación")

    instante = now or datetime.now(UTC)
    try:
        enviado = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AuthenticationError("Marca temporal de la petición inválida") from exc
    if enviado.tzinfo is None:
        enviado = enviado.replace(tzinfo=UTC)

    desfase = abs((instante - enviado).total_seconds())
    if desfase > max_skew_seconds:
        logger.warning("request_timestamp_out_of_window", client=cliente, skew_seconds=int(desfase))
        raise AuthenticationError("La petición está fuera de la ventana temporal admitida")

    esperada = sign_request(resolver.secret_for(cliente), method, path, timestamp, body)
    if not hmac.compare_digest(esperada, firma):
        logger.warning("invalid_request_signature", client=cliente)
        raise AuthenticationError("Firma de la petición inválida")

    return SecurityContext(b2b_client_id=cliente, principal=f"hmac:{cliente}")
