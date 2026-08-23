"""Repositorio de la pista de auditoría en Amazon DynamoDB.

Dos reglas estructurales, ambas verificadas en tiempo de ejecución:

1. **Aislamiento multi-tenant (ADR-0005).** Toda lectura y escritura exige un
   contexto de seguridad con ``b2b_client_id``. La comprobación vive aquí, no
   solo en la capa HTTP, para que un error de enrutamiento no se traduzca en una
   fuga entre inquilinos. No se expone ninguna operación de ``Scan``.
2. **Inmutabilidad (ADR-0003).** No hay operación de borrado ni de sobrescritura
   de una versión existente: una corrección crea ``METADATA#V{n+1}``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from pscnc.errors import EvidencePersistenceError, SigningSessionNotFoundError, TenantMismatchError
from pscnc.logging_setup import get_logger
from pscnc.models.audit_trail import AuditTrailItem

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class SecurityContext:
    """Identidad del cliente B2B autenticado que origina la operación."""

    b2b_client_id: str
    principal: str = ""

    def assert_owns(self, b2b_client_id: str) -> None:
        if b2b_client_id != self.b2b_client_id:
            logger.warning(
                "tenant_mismatch_blocked",
                context_tenant=self.b2b_client_id,
                requested_tenant=b2b_client_id,
            )
            raise TenantMismatchError("El recurso solicitado pertenece a otro cliente B2B")


def _to_dynamo(valor: Any) -> Any:
    """Convierte tipos de Python a los admitidos por DynamoDB."""
    if isinstance(valor, datetime):
        return valor.isoformat().replace("+00:00", "Z")
    if isinstance(valor, float):
        # DynamoDB no admite float: se usa Decimal para no perder precisión de los
        # puntajes biométricos, que son datos periciales.
        return Decimal(str(valor))
    if isinstance(valor, dict):
        return {k: _to_dynamo(v) for k, v in valor.items() if v is not None}
    if isinstance(valor, list):
        return [_to_dynamo(v) for v in valor]
    return valor


def _from_dynamo(valor: Any) -> Any:
    if isinstance(valor, Decimal):
        entero = int(valor)
        return entero if valor == entero else float(valor)
    if isinstance(valor, dict):
        return {k: _from_dynamo(v) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_from_dynamo(v) for v in valor]
    return valor


class AuditTrailRepository:
    """Acceso a la tabla `PSCNC_Audit_Trail`."""

    def __init__(self, table_name: str, *, region: str, resource: Any | None = None) -> None:
        self._table_name = table_name
        recurso = resource or boto3.resource(
            "dynamodb",
            region_name=region,
            config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
        )
        self._table = recurso.Table(table_name)

    # ---------------------------------------------------------- Escritura ----
    def put_new_version(self, item: AuditTrailItem, context: SecurityContext) -> None:
        """Escribe una versión del expediente sin sobrescribir ninguna anterior."""
        context.assert_owns(item.b2b_client_id)

        payload = _to_dynamo(item.model_dump(mode="python", exclude_none=True))
        try:
            self._table.put_item(
                Item=payload,
                # Garantiza que la versión no exista todavía: la evidencia no se pisa.
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code")
            if codigo == "ConditionalCheckFailedException":
                raise EvidencePersistenceError(
                    "Ya existe una versión con esa clave; la evidencia no se sobrescribe."
                ) from exc
            logger.error("audit_put_failed", transaction_id=item.transaction_id, error=str(exc))
            raise EvidencePersistenceError("No se pudo persistir la pista de auditoría") from exc

        logger.info(
            "audit_version_written",
            transaction_id=item.transaction_id,
            version=item.SK,
            status=item.status.value,
            b2b_client_id=item.b2b_client_id,
        )

    # ----------------------------------------------------------- Lectura -----
    def get_latest(self, transaction_id: str, context: SecurityContext) -> AuditTrailItem:
        """Devuelve la versión más reciente del expediente de una transacción."""
        try:
            respuesta = self._table.query(
                KeyConditionExpression=Key("PK").eq(f"TX#{transaction_id}"),
                ScanIndexForward=False,  # última versión primero
                Limit=1,
            )
        except ClientError as exc:
            logger.error("audit_query_failed", transaction_id=transaction_id, error=str(exc))
            raise EvidencePersistenceError("No se pudo consultar la pista de auditoría") from exc

        elementos = respuesta.get("Items", [])
        if not elementos:
            raise SigningSessionNotFoundError("No existe la sesión de firma solicitada")

        item = AuditTrailItem.model_validate(_from_dynamo(elementos[0]))
        context.assert_owns(item.b2b_client_id)
        return item

    def next_version_key(self, transaction_id: str) -> int:
        """Calcula el número de versión siguiente para una transacción."""
        respuesta = self._table.query(
            KeyConditionExpression=Key("PK").eq(f"TX#{transaction_id}"),
            ScanIndexForward=False,
            Limit=1,
            ProjectionExpression="SK",
        )
        elementos = respuesta.get("Items", [])
        if not elementos:
            return 1
        return int(str(elementos[0]["SK"]).removeprefix("METADATA#V")) + 1

    def list_by_tenant(
        self,
        context: SecurityContext,
        *,
        desde: datetime | None = None,
        hasta: datetime | None = None,
        limite: int = 50,
    ) -> list[AuditTrailItem]:
        """Lista transacciones del inquilino autenticado, ordenadas por fecha descendente."""
        condicion = Key("GSI2PK").eq(f"CLIENT#{context.b2b_client_id}")
        if desde and hasta:
            condicion = condicion & Key("GSI2SK").between(desde.isoformat(), hasta.isoformat())
        elif desde:
            condicion = condicion & Key("GSI2SK").gte(desde.isoformat())

        respuesta = self._table.query(
            IndexName="GSI2-Tenant",
            KeyConditionExpression=condicion,
            ScanIndexForward=False,
            Limit=min(limite, 200),
        )
        return [AuditTrailItem.model_validate(_from_dynamo(i)) for i in respuesta.get("Items", [])]

    def list_by_national_id(
        self, national_id: str, context: SecurityContext, *, limite: int = 50
    ) -> list[AuditTrailItem]:
        """Consulta pericial por cédula, restringida al inquilino autenticado.

        El filtro por inquilino se aplica después de la consulta al índice: el GSI1
        es global por diseño (una pericia necesita ver todas las firmas de una
        persona), pero un cliente B2B solo puede ver las suyas.
        """
        respuesta = self._table.query(
            IndexName="GSI1-Signer",
            KeyConditionExpression=Key("GSI1PK").eq(f"CI#PY-{national_id}"),
            ScanIndexForward=False,
            Limit=min(limite, 200),
        )
        items = [AuditTrailItem.model_validate(_from_dynamo(i)) for i in respuesta.get("Items", [])]
        return [i for i in items if i.b2b_client_id == context.b2b_client_id]
