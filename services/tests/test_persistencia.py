"""Persistencia en DynamoDB de transacciones e idempotencia (T-11).

El problema que esto resuelve: con los almacenes en memoria, **dos réplicas no
comparten estado**. Un reintento que cayera en otra instancia no encontraría la
clave de idempotencia y emitiría un acta nueva para el mismo acto de firma — dos
evidencias divergentes del mismo hecho, que es justo lo que la idempotencia
existe para impedir. Las pruebas de aquí ejercitan ese escenario de forma
explícita: dos repositorios distintos contra la misma tabla.

Se usa `moto`. Todos los datos son sintéticos.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import Any

import boto3
import pytest
from moto import mock_aws

from pscnc.errors import EvidencePersistenceError
from pscnc.models.v1 import OtpMode, ServiceLevel, TransactionStatus
from pscnc.orchestrator.idempotencia import IdempotencyControl, StoredResponse
from pscnc.orchestrator.transacciones import Transaction
from pscnc.repositories.dynamo_idempotencia import DynamoIdempotencyStore
from pscnc.repositories.dynamo_transacciones import DynamoTransactionRepository

REGION = "us-east-1"
TABLA_AUDITORIA = "PSCNC_Audit_Trail_Test"
TABLA_IDEMPOTENCIA = "PSCNC_Idempotency_Test"
TENANT = "segurolotengo"
TX = "c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb"
AHORA = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)


@pytest.fixture(autouse=True)
def credenciales_simuladas() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


@pytest.fixture()
def dynamo() -> Any:
    with mock_aws():
        recurso = boto3.resource("dynamodb", region_name=REGION)
        recurso.create_table(
            TableName=TABLA_AUDITORIA,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        recurso.create_table(
            TableName=TABLA_IDEMPOTENCIA,
            KeySchema=[{"AttributeName": "PK", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "PK", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        yield recurso


def _transaccion(**cambios: Any) -> Transaction:
    base: dict[str, Any] = {
        "transaction_id": TX,
        "tenant_id": TENANT,
        "tenant_reference": "EXP-99887",
        "jurisdiction": "PY",
        "service_level": ServiceLevel.SEALED_ACTA,
        "otp_mode": OtpMode.TENANT_VERIFIED,
        "document_sha256": "a" * 64,
        "document_version": 2,
        "document_code": "PROP-2026-000123",
        "document_closed_at": AHORA,
        "identity_approved": True,
        "created_at": AHORA,
        "expires_at": AHORA + timedelta(hours=1),
    }
    base.update(cambios)
    return Transaction(**base)


# -------------------------------------------------------- Transacciones ----
class TestRepositorioDeTransacciones:
    @pytest.fixture()
    def repo(self, dynamo: Any) -> DynamoTransactionRepository:
        return DynamoTransactionRepository(TABLA_AUDITORIA, region=REGION, resource=dynamo)

    def test_guarda_y_recupera_una_transaccion(self, repo: DynamoTransactionRepository) -> None:
        repo.guardar(_transaccion())

        recuperada = repo.obtener(TX)

        assert recuperada is not None
        assert recuperada.tenant_reference == "EXP-99887"
        assert recuperada.status is TransactionStatus.CREATED

    def test_una_transaccion_inexistente_devuelve_nada(
        self, repo: DynamoTransactionRepository
    ) -> None:
        assert repo.obtener("00000000-0000-4000-8000-000000000000") is None

    def test_el_cambio_de_estado_escribe_una_version_nueva(
        self, repo: DynamoTransactionRepository, dynamo: Any
    ) -> None:
        """Append-only: la versión anterior permanece.

        Un perito tiene que poder reconstruir que la transacción existió como
        `CREATED` antes de confirmarse; una actualización en el lugar lo
        destruiría sin dejar rastro.
        """
        repo.guardar(_transaccion())
        repo.guardar(
            _transaccion(
                status=TransactionStatus.CONFIRMED,
                confirmed_at=AHORA + timedelta(minutes=1),
                verification_code="ABCDEFGH2345",
                acta_jws="c.p.f",
                acta_payload_sha256="b" * 64,
                acta_key_alias="alias/fnc/dev/segurolotengo/acta-seal/v1",
            )
        )

        versiones = dynamo.Table(TABLA_AUDITORIA).query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PK").eq(f"TX#{TX}")
            & boto3.dynamodb.conditions.Key("SK").begins_with("TXV1#V")
        )["Items"]

        assert len(versiones) == 2
        assert {v["SK"] for v in versiones} == {"TXV1#V1", "TXV1#V2"}

    def test_la_lectura_devuelve_la_version_mas_reciente(
        self, repo: DynamoTransactionRepository
    ) -> None:
        repo.guardar(_transaccion())
        repo.guardar(
            _transaccion(
                status=TransactionStatus.CONFIRMED,
                verification_code="ABCDEFGH2345",
                acta_jws="c.p.f",
            )
        )

        assert repo.obtener(TX).status is TransactionStatus.CONFIRMED  # type: ignore[union-attr]

    def test_recupera_por_codigo_de_verificacion(self, repo: DynamoTransactionRepository) -> None:
        """La verificación pública busca por código, no por identificador."""
        repo.guardar(
            _transaccion(
                status=TransactionStatus.CONFIRMED,
                verification_code="ABCDEFGH2345",
                acta_jws="c.p.f",
            )
        )

        recuperada = repo.obtener_por_codigo("ABCDEFGH2345")

        assert recuperada is not None
        assert recuperada.transaction_id == TX

    def test_un_codigo_inexistente_devuelve_nada(self, repo: DynamoTransactionRepository) -> None:
        assert repo.obtener_por_codigo("ZZZZZZZZZZZZ") is None

    def test_un_codigo_de_otra_transaccion_no_se_reasigna(
        self, repo: DynamoTransactionRepository
    ) -> None:
        """Una colisión de código se rechaza en vez de reasignarse en silencio."""
        repo.guardar(
            _transaccion(status=TransactionStatus.CONFIRMED, verification_code="ABCDEFGH2345")
        )

        with pytest.raises(EvidencePersistenceError, match="ya pertenece a otra"):
            repo.guardar(
                _transaccion(
                    transaction_id="d1af4e4c-68ad-48f1-a2c0-b0a9476f06dc",
                    status=TransactionStatus.CONFIRMED,
                    verification_code="ABCDEFGH2345",
                )
            )

    def test_los_campos_del_nivel_2_sobreviven_al_viaje(
        self, repo: DynamoTransactionRepository
    ) -> None:
        repo.guardar(
            _transaccion(
                service_level=ServiceLevel.PADES,
                status=TransactionStatus.CONFIRMED,
                verification_code="ABCDEFGH2346",
                signed_document_sha256="c" * 64,
                signer_certificate_serial="7857fdf7e9",
                timestamp_authority="TSA de Pruebas",
            )
        )

        recuperada = repo.obtener(TX)

        assert recuperada is not None
        assert recuperada.service_level is ServiceLevel.PADES
        assert recuperada.signed_document_sha256 == "c" * 64
        assert recuperada.signer_certificate_serial == "7857fdf7e9"

    def test_dos_replicas_ven_la_misma_transaccion(self, dynamo: Any) -> None:
        """El problema que T-11 resuelve, comprobado de forma directa."""
        una = DynamoTransactionRepository(TABLA_AUDITORIA, region=REGION, resource=dynamo)
        otra = DynamoTransactionRepository(TABLA_AUDITORIA, region=REGION, resource=dynamo)

        una.guardar(_transaccion())

        assert otra.obtener(TX) is not None


# -------------------------------------------------------- Idempotencia -----
class TestAlmacenDeIdempotencia:
    @pytest.fixture()
    def almacen(self, dynamo: Any) -> DynamoIdempotencyStore:
        return DynamoIdempotencyStore(
            TABLA_IDEMPOTENCIA,
            region=REGION,
            ventana=timedelta(hours=24),
            resource=dynamo,
        )

    def test_guarda_y_recupera_una_respuesta(self, almacen: DynamoIdempotencyStore) -> None:
        almacen.guardar(
            "tenant:k-1",
            StoredResponse(
                status_code=201,
                body={"transaction_id": TX},
                request_sha256="d" * 64,
                stored_at=AHORA,
            ),
        )

        recuperada = almacen.obtener("tenant:k-1")

        assert recuperada is not None
        assert recuperada.status_code == 201
        assert recuperada.body["transaction_id"] == TX

    def test_una_clave_desconocida_devuelve_nada(self, almacen: DynamoIdempotencyStore) -> None:
        assert almacen.obtener("tenant:jamas-usada") is None

    def test_el_item_lleva_expiracion_nativa(
        self, almacen: DynamoIdempotencyStore, dynamo: Any
    ) -> None:
        """El TTL evita que la tabla crezca sin límite.

        Solo existe en esta tabla: la de auditoría no lo tiene, porque su
        contenido no puede expirar.
        """
        almacen.guardar(
            "tenant:k-2",
            StoredResponse(status_code=200, body={}, request_sha256="e" * 64, stored_at=AHORA),
        )

        item = dynamo.Table(TABLA_IDEMPOTENCIA).get_item(Key={"PK": "tenant:k-2"})["Item"]

        assert int(item["expires_at"]) > AHORA.timestamp()

    def test_los_numeros_decimales_sobreviven_al_viaje(
        self, almacen: DynamoIdempotencyStore
    ) -> None:
        """DynamoDB no admite `float`; la conversión no puede perder precisión.

        El cuerpo guardado incluye puntajes biométricos, que son dato pericial.
        """
        almacen.guardar(
            "tenant:k-3",
            StoredResponse(
                status_code=200,
                body={"score": 0.995, "anidado": {"umbral": 0.99}},
                request_sha256="f" * 64,
                stored_at=AHORA,
            ),
        )

        recuperada = almacen.obtener("tenant:k-3")

        assert recuperada is not None
        assert recuperada.body["score"] == 0.995
        assert recuperada.body["anidado"]["umbral"] == 0.99

    def test_dos_replicas_comparten_la_idempotencia(self, dynamo: Any) -> None:
        """El escenario exacto que los almacenes en memoria no cubrían.

        Con memoria local, el reintento que cae en otra instancia emite un acta
        nueva para el mismo acto de firma.
        """
        control_a = IdempotencyControl(
            DynamoIdempotencyStore(
                TABLA_IDEMPOTENCIA,
                region=REGION,
                ventana=timedelta(hours=24),
                resource=dynamo,
            )
        )
        control_b = IdempotencyControl(
            DynamoIdempotencyStore(
                TABLA_IDEMPOTENCIA,
                region=REGION,
                ventana=timedelta(hours=24),
                resource=dynamo,
            )
        )

        control_a.registrar(
            tenant_id=TENANT,
            clave="k-compartida",
            ruta="/v1/transactions",
            cuerpo=b'{"a":1}',
            status_code=201,
            body={"transaction_id": TX},
        )

        recuperada = control_b.recuperar(
            tenant_id=TENANT,
            clave="k-compartida",
            ruta="/v1/transactions",
            cuerpo=b'{"a":1}',
        )

        assert recuperada is not None
        assert recuperada.body["transaction_id"] == TX

    def test_el_conflicto_se_detecta_entre_replicas(self, dynamo: Any) -> None:
        """La misma clave con otro cuerpo, aunque llegue a otra instancia."""
        from pscnc.orchestrator.idempotencia import IdempotencyConflictError

        control_a = IdempotencyControl(
            DynamoIdempotencyStore(
                TABLA_IDEMPOTENCIA, region=REGION, ventana=timedelta(hours=24), resource=dynamo
            )
        )
        control_b = IdempotencyControl(
            DynamoIdempotencyStore(
                TABLA_IDEMPOTENCIA, region=REGION, ventana=timedelta(hours=24), resource=dynamo
            )
        )
        control_a.registrar(
            tenant_id=TENANT,
            clave="k-conflicto",
            ruta="/v1/transactions",
            cuerpo=b'{"a":1}',
            status_code=201,
            body={},
        )

        with pytest.raises(IdempotencyConflictError):
            control_b.recuperar(
                tenant_id=TENANT,
                clave="k-conflicto",
                ruta="/v1/transactions",
                cuerpo=b'{"a":2}',
            )
