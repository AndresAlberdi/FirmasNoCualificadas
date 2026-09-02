"""Almacén de idempotencia en DynamoDB con expiración nativa (T-11).

## Por qué una tabla propia y no la de auditoría

La pista de auditoría **no puede expirar**: su plazo de conservación es una
obligación legal y el ADR-0003 la protege incluso frente al usuario raíz. Los
registros de idempotencia, en cambio, deben expirar: retenerlos para siempre
convertiría el almacén en un registro paralelo de toda la actividad del servicio.

Habilitar TTL sobre la tabla de auditoría para servir al segundo caso pondría un
mecanismo de borrado automático en la misma tabla que guarda lo que no puede
borrarse. Bastaría que un ítem de evidencia recibiera por error el atributo de
expiración —un `model_dump` de más, un campo mal copiado— para que DynamoDB lo
eliminara en silencio, sin registro y sin forma de recuperarlo. La separación
elimina esa clase de error por completo, y cuesta una tabla.

## Por qué el TTL de DynamoDB alcanza acá

La expiración de DynamoDB no es inmediata: puede tardar hasta 48 horas. Para
evidencia sería inaceptable; para idempotencia es irrelevante, porque el control
comprueba la ventana al leer y descarta una entrada vencida aunque siga
almacenada. El TTL solo evita que la tabla crezca sin límite.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from pscnc.logging_setup import get_logger
from pscnc.orchestrator.idempotencia import StoredResponse

logger = get_logger(__name__)

#: Margen que se suma a la ventana para calcular la expiración física. La lectura
#: ya descarta lo vencido, así que conservar de más no cambia el comportamiento;
#: conservar de menos haría que un reintento legítimo no encuentre su respuesta.
MARGEN_DE_EXPIRACION = timedelta(hours=24)


class DynamoIdempotencyStore:
    """Implementación del almacén sobre una tabla dedicada."""

    def __init__(
        self,
        table_name: str,
        *,
        region: str,
        ventana: timedelta,
        resource: Any | None = None,
    ) -> None:
        self._table_name = table_name
        self._ventana = ventana
        recurso = resource or boto3.resource(
            "dynamodb",
            region_name=region,
            config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
        )
        self._table = recurso.Table(table_name)

    def obtener(self, clave: str) -> StoredResponse | None:
        try:
            respuesta = self._table.get_item(Key={"PK": clave})
        except ClientError as exc:
            # Un fallo al leer no puede hacerse pasar por «no hay respuesta
            # guardada»: eso ejecutaría la operación otra vez y emitiría un acta
            # nueva, que es exactamente lo que la idempotencia existe para evitar.
            logger.error("idempotency_read_failed", error=str(exc))
            raise

        item = respuesta.get("Item")
        if item is None:
            return None

        return StoredResponse(
            status_code=int(str(item["status_code"])),
            body=_desde_dynamo(item["body"]),
            request_sha256=str(item["request_sha256"]),
            stored_at=datetime.fromisoformat(str(item["stored_at"])),
        )

    def guardar(self, clave: str, respuesta: StoredResponse) -> None:
        expira = respuesta.stored_at + self._ventana + MARGEN_DE_EXPIRACION

        try:
            self._table.put_item(
                Item={
                    "PK": clave,
                    "status_code": respuesta.status_code,
                    "body": _a_dynamo(respuesta.body),
                    "request_sha256": respuesta.request_sha256,
                    "stored_at": respuesta.stored_at.isoformat(),
                    # Atributo que DynamoDB usa para expirar el ítem, en segundos
                    # desde época. Solo existe en esta tabla.
                    "expires_at": int(expira.timestamp()),
                }
            )
        except ClientError as exc:
            logger.error("idempotency_write_failed", error=str(exc))
            raise


def _a_dynamo(valor: Any) -> Any:
    """DynamoDB no admite `float`: se convierte a `Decimal` sin perder dígitos."""
    if isinstance(valor, float):
        return Decimal(str(valor))
    if isinstance(valor, dict):
        return {k: _a_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_a_dynamo(v) for v in valor]
    return valor


def _desde_dynamo(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        entero = int(valor)
        return entero if valor == entero else float(valor)
    if isinstance(valor, dict):
        return {k: _desde_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_desde_dynamo(v) for v in valor]
    return valor


def ahora_utc() -> datetime:
    return datetime.now(UTC)
