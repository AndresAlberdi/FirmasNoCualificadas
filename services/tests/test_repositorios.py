"""Pruebas de los repositorios contra AWS simulado con ``moto``.

Cubren dos reglas inviolables que hasta ahora solo estaban garantizadas por
construcción, sin prueba que lo demostrara:

* **Evidencia append-only** (regla 5): una versión existente no se sobrescribe.
* **Aislamiento multi-tenant en la capa de datos** (regla 6): la comprobación
  vive en el repositorio, no solo en HTTP, para que un error de enrutamiento no
  se convierta en una fuga entre inquilinos (ADR-0005).

Todos los datos son sintéticos (ver CONTRIBUTING.md).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from botocore.config import Config as BotoConfig
from moto import mock_aws

from pscnc.errors import (
    EvidencePersistenceError,
    SigningSessionNotFoundError,
    TenantMismatchError,
)
from pscnc.models.audit_trail import AuditTrailItem, SigningStatus
from pscnc.repositories.dynamo_audit import AuditTrailRepository, SecurityContext
from pscnc.repositories.s3_vault import DocumentVault

REGION = "us-east-1"
TABLA = "PSCNC_Audit_Trail_Test"
BUCKET_FIRMADOS = "pscnc-test-firmados"
BUCKET_EVIDENCIAS = "pscnc-test-evidencias"

TENANT_A = "aseguradora-a"
TENANT_B = "aseguradora-b"
TX_A = "c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb"
TX_B = "d1af4e4c-68ad-48f1-a2c0-b0a9476f06dc"


@pytest.fixture(autouse=True)
def credenciales_simuladas() -> None:
    """`moto` exige credenciales presentes; nunca se usan contra AWS real."""
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


def _crear_tabla(recurso: Any) -> None:
    """Réplica del esquema de `infra/terraform/modules/audit-trail-dynamodb`."""
    recurso.create_table(
        TableName=TABLA,
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
            {"AttributeName": "GSI2PK", "AttributeType": "S"},
            {"AttributeName": "GSI2SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1-Signer",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "GSI2-Tenant",
                "KeySchema": [
                    {"AttributeName": "GSI2PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI2SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
        BillingMode="PAY_PER_REQUEST",
    )


def _item(
    identidad: Any,
    red: Any,
    *,
    transaction_id: str = TX_A,
    tenant: str = TENANT_A,
    version: int = 1,
    filename: str = "contrato.pdf",
) -> AuditTrailItem:
    creado = datetime(2026, 9, 2, 12, 0, 0, tzinfo=UTC)
    return AuditTrailItem(
        **AuditTrailItem.build_keys(  # type: ignore[arg-type]
            transaction_id=transaction_id,
            national_id=identidad.national_id,
            b2b_client_id=tenant,
            created_at=creado,
            version=version,
        ),
        transaction_id=transaction_id,
        b2b_client_id=tenant,
        status=SigningStatus.INITIALIZED,
        created_at=creado,
        document_filename=filename,
        identity_evidence=identidad,
        network_evidence=red,
    )


# ---------------------------------------------------------------- DynamoDB ---
class TestPistaDeAuditoria:
    @pytest.fixture()
    def repo(self) -> Any:
        with mock_aws():
            recurso = boto3.resource("dynamodb", region_name=REGION)
            _crear_tabla(recurso)
            yield AuditTrailRepository(TABLA, region=REGION, resource=recurso)

    def test_escribe_y_recupera_la_version_vigente(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        contexto = SecurityContext(b2b_client_id=TENANT_A)
        repo.put_new_version(_item(identidad, red), contexto)

        recuperado = repo.get_latest(TX_A, contexto)

        assert recuperado.transaction_id == TX_A
        assert recuperado.status is SigningStatus.INITIALIZED

    def test_no_sobrescribe_una_version_existente(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        """Regla inviolable 5: la evidencia es append-only.

        Reescribir `METADATA#V1` con otro contenido destruiría la prueba del
        estado anterior, que es justamente lo que una pericia necesita.
        """
        contexto = SecurityContext(b2b_client_id=TENANT_A)
        repo.put_new_version(_item(identidad, red), contexto)

        with pytest.raises(EvidencePersistenceError):
            repo.put_new_version(_item(identidad, red, filename="suplantado.pdf"), contexto)

        # El contenido original sobrevive al intento de sobrescritura.
        assert repo.get_latest(TX_A, contexto).document_filename == "contrato.pdf"

    def test_una_correccion_crea_una_version_nueva(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        contexto = SecurityContext(b2b_client_id=TENANT_A)
        repo.put_new_version(_item(identidad, red), contexto)

        assert repo.next_version_key(TX_A) == 2

        repo.put_new_version(_item(identidad, red, version=2, filename="corregido.pdf"), contexto)

        # `get_latest` devuelve la versión más alta, y la anterior sigue existiendo.
        assert repo.get_latest(TX_A, contexto).document_filename == "corregido.pdf"
        assert repo.next_version_key(TX_A) == 3

    def test_version_inicial_de_una_transaccion_inexistente(self, repo) -> None:  # type: ignore[no-untyped-def]
        assert repo.next_version_key("00000000-0000-4000-8000-000000000000") == 1

    def test_transaccion_inexistente(self, repo) -> None:  # type: ignore[no-untyped-def]
        with pytest.raises(SigningSessionNotFoundError):
            repo.get_latest(TX_A, SecurityContext(b2b_client_id=TENANT_A))

    def test_no_se_puede_escribir_a_nombre_de_otro_inquilino(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        """El contexto de seguridad manda sobre el contenido del ítem."""
        with pytest.raises(TenantMismatchError):
            repo.put_new_version(
                _item(identidad, red, tenant=TENANT_B), SecurityContext(b2b_client_id=TENANT_A)
            )

    def test_no_se_puede_leer_la_transaccion_de_otro_inquilino(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        """Regla inviolable 6: la comprobación vive en el repositorio.

        Aunque el identificador de transacción sea correcto y el llamador esté
        autenticado, el inquilino del contexto decide.
        """
        repo.put_new_version(_item(identidad, red), SecurityContext(b2b_client_id=TENANT_A))

        with pytest.raises(TenantMismatchError):
            repo.get_latest(TX_A, SecurityContext(b2b_client_id=TENANT_B))

    def test_listado_por_inquilino_solo_devuelve_lo_propio(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        repo.put_new_version(_item(identidad, red), SecurityContext(b2b_client_id=TENANT_A))
        repo.put_new_version(
            _item(identidad, red, transaction_id=TX_B, tenant=TENANT_B),
            SecurityContext(b2b_client_id=TENANT_B),
        )

        del_a = repo.list_by_tenant(SecurityContext(b2b_client_id=TENANT_A))

        assert [i.transaction_id for i in del_a] == [TX_A]

    def test_consulta_pericial_por_cedula_se_restringe_al_inquilino(  # type: ignore[no-untyped-def]
        self, repo, identidad, red
    ) -> None:
        """El GSI1 es global por diseño; el filtro por inquilino se aplica después.

        Una pericia necesita poder ver todas las firmas de una persona, pero un
        cliente B2B solo puede ver las suyas.
        """
        repo.put_new_version(_item(identidad, red), SecurityContext(b2b_client_id=TENANT_A))
        repo.put_new_version(
            _item(identidad, red, transaction_id=TX_B, tenant=TENANT_B),
            SecurityContext(b2b_client_id=TENANT_B),
        )

        resultado = repo.list_by_national_id(
            identidad.national_id, SecurityContext(b2b_client_id=TENANT_A)
        )

        assert [i.transaction_id for i in resultado] == [TX_A]

    def test_los_puntajes_biometricos_conservan_su_precision(self, repo, identidad, red) -> None:  # type: ignore[no-untyped-def]
        """DynamoDB no admite `float`: se convierte a `Decimal` sin perder dígitos.

        El puntaje es un dato pericial; redondearlo alteraría la evidencia.
        """
        contexto = SecurityContext(b2b_client_id=TENANT_A)
        repo.put_new_version(_item(identidad, red), contexto)

        assert repo.get_latest(TX_A, contexto).identity_evidence.facial_match_score == 0.985


# ----------------------------------------------------------------- S3 -------
class TestBovedaDeDocumentos:
    @pytest.fixture()
    def vault(self) -> Any:
        with mock_aws():
            # Misma configuración de firma que en producción: una URL v2 y una v4
            # no tienen los mismos parámetros, y el test verifica esos parámetros.
            cliente = boto3.client(
                "s3",
                region_name=REGION,
                config=BotoConfig(signature_version="s3v4"),
            )
            cliente.create_bucket(Bucket=BUCKET_FIRMADOS)
            cliente.create_bucket(Bucket=BUCKET_EVIDENCIAS)
            yield DocumentVault(
                signed_bucket=BUCKET_FIRMADOS,
                evidence_bucket=BUCKET_EVIDENCIAS,
                region=REGION,
                client=cliente,
            )

    def test_las_claves_llevan_el_prefijo_del_inquilino(self) -> None:
        """Aislamiento también en el almacenamiento (ADR-0005, capa 3)."""
        assert DocumentVault.signed_key(TENANT_A, TX_A).startswith(f"{TENANT_A}/")
        assert DocumentVault.evidence_key(TENANT_A, TX_A).startswith(f"{TENANT_A}/")
        assert DocumentVault.original_key(TENANT_A, TX_A).startswith(f"{TENANT_A}/")

    def test_dos_inquilinos_no_comparten_ruta(self) -> None:
        assert DocumentVault.signed_key(TENANT_A, TX_A) != DocumentVault.signed_key(TENANT_B, TX_A)

    def test_guarda_y_recupera_el_documento_original(self, vault) -> None:  # type: ignore[no-untyped-def]
        contenido = b"%PDF-1.7 documento de prueba"
        vault.put_original_document(
            b2b_client_id=TENANT_A, transaction_id=TX_A, content=contenido, sha256="a" * 64
        )

        assert vault.get_original_document(b2b_client_id=TENANT_A, transaction_id=TX_A) == contenido

    def test_el_original_de_un_inquilino_no_es_visible_para_otro(self, vault) -> None:  # type: ignore[no-untyped-def]
        vault.put_original_document(
            b2b_client_id=TENANT_A, transaction_id=TX_A, content=b"%PDF-1.7 A", sha256="a" * 64
        )

        with pytest.raises(EvidencePersistenceError):
            vault.get_original_document(b2b_client_id=TENANT_B, transaction_id=TX_A)

    def test_registra_la_huella_como_metadato_del_objeto(self, vault) -> None:  # type: ignore[no-untyped-def]
        """Permite verificar la integridad sin descargar el binario completo."""
        vault.put_signed_document(
            b2b_client_id=TENANT_A, transaction_id=TX_A, content=b"%PDF-1.7 f", sha256="b" * 64
        )

        cabecera = boto3.client("s3", region_name=REGION).head_object(
            Bucket=BUCKET_FIRMADOS, Key=DocumentVault.signed_key(TENANT_A, TX_A)
        )

        assert cabecera["Metadata"]["sha256"] == "b" * 64
        assert cabecera["Metadata"]["transaction-id"] == TX_A

    def test_guarda_el_expediente_en_el_bucket_de_evidencias(self, vault) -> None:  # type: ignore[no-untyped-def]
        """El expediente va al bucket con Object Lock, separado del firmado."""
        almacenado = vault.put_evidence_report(
            b2b_client_id=TENANT_A, transaction_id=TX_A, content=b"%PDF-1.7 e", sha256="c" * 64
        )

        assert almacenado.bucket == BUCKET_EVIDENCIAS

    def test_la_url_prefirmada_caduca(self, vault) -> None:  # type: ignore[no-untyped-def]
        url = vault.presigned_signed_document(TENANT_A, TX_A)

        assert "X-Amz-Expires=300" in url
        assert DocumentVault.signed_key(TENANT_A, TX_A) in url

    def test_recuperar_un_original_inexistente_es_un_error_de_dominio(self, vault) -> None:  # type: ignore[no-untyped-def]
        """El error de AWS no se propaga crudo: se traduce al dominio."""
        with pytest.raises(EvidencePersistenceError):
            vault.get_original_document(b2b_client_id=TENANT_A, transaction_id=TX_B)
