"""Persistencia de las transacciones del contrato v1 (T-11, ADR-0003).

Vive en la tabla única de la pista de auditoría, porque una transacción de firma
**es** pista de auditoría: su historia —cuándo se abrió, con qué documento, cuándo
se confirmó y con qué acta— es lo que se exhibe ante una pericia.

## Append-only, igual que el resto de la evidencia

Una transacción cambia de estado, pero el cambio **no sobrescribe**: cada estado
escribe `TXV1#V{n+1}` y el anterior permanece. La lectura devuelve la versión más
alta. Así, el registro conserva que la transacción existió como `CREATED` antes de
confirmarse, que es justo lo que un perito necesita para reconstruir la secuencia
—y lo que una actualización en el lugar destruiría sin dejar rastro.

## El puntero del código de verificación

`GET /v1/verify/{code}` busca por un código público, no por identificador. En
lugar de agregar un índice secundario global, se escribe un ítem puntero
`VERIFY#{code}` que apunta a la transacción. Dos razones: el código se acuña una
sola vez y nunca cambia, de modo que el puntero no necesita mantenimiento; y un
índice adicional se proyecta entero, lo que duplicaría el almacenamiento de una
tabla cuyo contenido no expira.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.config import Config as BotoConfig
from botocore.exceptions import ClientError

from pscnc.errors import EvidencePersistenceError
from pscnc.logging_setup import get_logger
from pscnc.models.v1 import ServiceLevel, TransactionStatus
from pscnc.orchestrator.transacciones import Transaction

logger = get_logger(__name__)

PREFIJO_VERSION = "TXV1#V"


class DynamoTransactionRepository:
    """Repositorio de transacciones sobre la tabla de auditoría."""

    def __init__(self, table_name: str, *, region: str, resource: Any | None = None) -> None:
        self._table_name = table_name
        recurso = resource or boto3.resource(
            "dynamodb",
            region_name=region,
            config=BotoConfig(retries={"max_attempts": 5, "mode": "standard"}),
        )
        self._table = recurso.Table(table_name)

    # ---------------------------------------------------------- Escritura ---
    def guardar(self, transaccion: Transaction) -> None:
        """Escribe una versión nueva del estado de la transacción.

        No sobrescribe: la condición exige que la clave no exista todavía. Si dos
        procesos intentan confirmar la misma transacción a la vez, uno de los dos
        falla en lugar de que el segundo pise la evidencia del primero.
        """
        version = self._proxima_version(transaccion.transaction_id)

        item = {
            "PK": f"TX#{transaccion.transaction_id}",
            "SK": f"{PREFIJO_VERSION}{version}",
            "GSI2PK": f"CLIENT#{transaccion.tenant_id}",
            "GSI2SK": transaccion.created_at.isoformat(),
            **_serializar(transaccion),
        }

        try:
            self._table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(PK) AND attribute_not_exists(SK)",
            )
        except ClientError as exc:
            codigo = exc.response.get("Error", {}).get("Code")
            if codigo == "ConditionalCheckFailedException":
                raise EvidencePersistenceError(
                    "Otra escritura ganó la carrera sobre esta transacción; "
                    "la evidencia no se sobrescribe."
                ) from exc
            logger.error(
                "transaction_write_failed",
                transaction_id=transaccion.transaction_id,
                error=str(exc),
            )
            raise EvidencePersistenceError("No se pudo persistir la transacción") from exc

        # El puntero se escribe después del estado, y solo cuando hay código: si
        # se escribiera antes, una consulta pública podría encontrar el puntero y
        # no la transacción a la que apunta.
        if transaccion.verification_code:
            self._guardar_puntero(transaccion)

        logger.info(
            "transaction_version_written",
            transaction_id=transaccion.transaction_id,
            version=version,
            status=transaccion.status.value,
        )

    def _guardar_puntero(self, transaccion: Transaction) -> None:
        try:
            self._table.put_item(
                Item={
                    "PK": f"VERIFY#{transaccion.verification_code}",
                    "SK": "POINTER",
                    "transaction_id": transaccion.transaction_id,
                },
                # Un código ya usado apuntando a otra transacción sería una
                # colisión: se prefiere fallar a reasignarlo en silencio.
                ConditionExpression="attribute_not_exists(PK)",
            )
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                # El puntero ya existe. Si apunta a esta misma transacción es una
                # reescritura del mismo estado y no hay nada que hacer.
                existente = self._table.get_item(
                    Key={"PK": f"VERIFY#{transaccion.verification_code}", "SK": "POINTER"}
                ).get("Item")
                if existente and existente.get("transaction_id") == transaccion.transaction_id:
                    return
                logger.error(
                    "verification_code_collision",
                    transaction_id=transaccion.transaction_id,
                )
                raise EvidencePersistenceError(
                    "El código de verificación ya pertenece a otra transacción."
                ) from exc
            raise

    # ----------------------------------------------------------- Lectura ----
    def obtener(self, transaction_id: str) -> Transaction | None:
        """Devuelve la versión más reciente de la transacción."""
        try:
            respuesta = self._table.query(
                KeyConditionExpression=Key("PK").eq(f"TX#{transaction_id}")
                & Key("SK").begins_with(PREFIJO_VERSION),
                ScanIndexForward=False,  # la versión más alta primero
                Limit=1,
            )
        except ClientError as exc:
            logger.error("transaction_read_failed", transaction_id=transaction_id)
            raise EvidencePersistenceError("No se pudo consultar la transacción") from exc

        elementos = respuesta.get("Items", [])
        return _deserializar(elementos[0]) if elementos else None

    def obtener_por_codigo(self, codigo: str) -> Transaction | None:
        puntero = self._table.get_item(Key={"PK": f"VERIFY#{codigo}", "SK": "POINTER"}).get("Item")
        if puntero is None:
            return None
        return self.obtener(str(puntero["transaction_id"]))

    # ------------------------------------------------------------ Interno ---
    def _proxima_version(self, transaction_id: str) -> int:
        respuesta = self._table.query(
            KeyConditionExpression=Key("PK").eq(f"TX#{transaction_id}")
            & Key("SK").begins_with(PREFIJO_VERSION),
            ScanIndexForward=False,
            Limit=1,
            ProjectionExpression="SK",
        )
        elementos = respuesta.get("Items", [])
        if not elementos:
            return 1
        return int(str(elementos[0]["SK"]).removeprefix(PREFIJO_VERSION)) + 1


def _serializar(t: Transaction) -> dict[str, Any]:
    """Vuelca la transacción a atributos de DynamoDB.

    Se omiten los campos vacíos en lugar de escribirlos nulos: un atributo
    ausente y uno presente en nulo se distinguen al leer, y el primero expresa
    mejor «todavía no ocurrió».
    """
    datos: dict[str, Any] = {
        "transaction_id": t.transaction_id,
        "tenant_id": t.tenant_id,
        "tenant_reference": t.tenant_reference,
        "jurisdiction": t.jurisdiction,
        "service_level": t.service_level.value,
        "otp_mode": t.otp_mode.value,
        "document_sha256": t.document_sha256,
        "document_version": t.document_version,
        "document_code": t.document_code,
        "document_closed_at": t.document_closed_at.isoformat(),
        "identity_approved": t.identity_approved,
        "created_at": t.created_at.isoformat(),
        "expires_at": t.expires_at.isoformat(),
        "status": t.status.value,
    }
    opcionales = {
        "confirmed_at": t.confirmed_at.isoformat() if t.confirmed_at else None,
        "verification_code": t.verification_code,
        "acta_jws": t.acta_jws,
        "acta_payload_sha256": t.acta_payload_sha256,
        "acta_key_alias": t.acta_key_alias,
        "signed_document_sha256": t.signed_document_sha256,
        "signer_certificate_serial": t.signer_certificate_serial,
        "timestamp_authority": t.timestamp_authority,
    }
    datos.update({k: v for k, v in opcionales.items() if v is not None})
    return datos


def _deserializar(item: dict[str, Any]) -> Transaction:
    def fecha(clave: str) -> datetime | None:
        valor = item.get(clave)
        return datetime.fromisoformat(str(valor)) if valor else None

    def entero(clave: str) -> int:
        # DynamoDB devuelve los números como `Decimal`; `int` los convierte igual.
        return int(item[clave])

    creado = fecha("created_at")
    cerrado = fecha("document_closed_at")
    expira = fecha("expires_at")
    assert creado is not None and cerrado is not None and expira is not None

    return Transaction(
        transaction_id=str(item["transaction_id"]),
        tenant_id=str(item["tenant_id"]),
        tenant_reference=str(item["tenant_reference"]),
        jurisdiction=str(item["jurisdiction"]),
        service_level=ServiceLevel(str(item["service_level"])),
        otp_mode=item["otp_mode"],
        document_sha256=str(item["document_sha256"]),
        document_version=entero("document_version"),
        document_code=str(item["document_code"]),
        document_closed_at=cerrado,
        identity_approved=bool(item["identity_approved"]),
        created_at=creado,
        expires_at=expira,
        status=TransactionStatus(str(item["status"])),
        confirmed_at=fecha("confirmed_at"),
        verification_code=_texto(item.get("verification_code")),
        acta_jws=_texto(item.get("acta_jws")),
        acta_payload_sha256=_texto(item.get("acta_payload_sha256")),
        acta_key_alias=_texto(item.get("acta_key_alias")),
        signed_document_sha256=_texto(item.get("signed_document_sha256")),
        signer_certificate_serial=_texto(item.get("signer_certificate_serial")),
        timestamp_authority=_texto(item.get("timestamp_authority")),
    )


def _texto(valor: Any) -> str | None:
    return str(valor) if valor is not None else None
