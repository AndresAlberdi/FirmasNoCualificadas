"""Aislamiento criptográfico entre inquilinos (ADR-0006, reglas inviolables 7, 9 y 10).

Estas pruebas cubren lo que el ADR-0005 no podía garantizar por sí solo. Aquel
aísla a los inquilinos comprobando el contexto de seguridad en el repositorio;
esto lleva el aislamiento a la capa criptográfica, donde no depende de que el
código recuerde comprobar nada: si el contexto no coincide, KMS se niega a
descifrar.

La distinción importa. Un control que vive solo en el código falla igual que el
código; un control que vive en la política de la clave sigue en pie aunque el
código tenga un error de enrutamiento.

Se ejercita contra KMS simulado con `moto`. Todos los datos son sintéticos.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

import boto3
import pytest
from moto import mock_aws

from pscnc.crypto.tenant_keys import (
    ALGORITMO_SELLO,
    CrossTenantKeyAccessError,
    KeyAliases,
    TenantKeyError,
    TenantKeyRing,
)
from pscnc.errors import SigningError

REGION = "us-east-1"
ENTORNO = "dev"
TENANT_A = "aseguradora-a"
TENANT_B = "aseguradora-b"
TX_A = "c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb"
TX_B = "d1af4e4c-68ad-48f1-a2c0-b0a9476f06dc"


@pytest.fixture(autouse=True)
def credenciales_simuladas() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


def _crear_claves(cliente: Any, tenant: str) -> None:
    """Réplica de lo que crea `modules/kms-tenant-keys` para un inquilino."""
    sello = cliente.create_key(
        Description=f"acta-seal {tenant}",
        KeyUsage="SIGN_VERIFY",
        KeySpec="ECC_NIST_P256",
    )["KeyMetadata"]["KeyId"]
    cliente.create_alias(AliasName=f"alias/fnc/{ENTORNO}/{tenant}/acta-seal/v1", TargetKeyId=sello)

    evidencias = cliente.create_key(
        Description=f"evidence {tenant}",
        KeyUsage="ENCRYPT_DECRYPT",
        KeySpec="SYMMETRIC_DEFAULT",
    )["KeyMetadata"]["KeyId"]
    cliente.create_alias(
        AliasName=f"alias/fnc/{ENTORNO}/{tenant}/evidence/v1", TargetKeyId=evidencias
    )


@pytest.fixture()
def kms() -> Any:
    with mock_aws():
        cliente = boto3.client("kms", region_name=REGION)
        _crear_claves(cliente, TENANT_A)
        _crear_claves(cliente, TENANT_B)
        yield cliente


@pytest.fixture()
def llavero_a(kms: Any) -> TenantKeyRing:
    return TenantKeyRing(TENANT_A, environment=ENTORNO, region=REGION, client=kms)


@pytest.fixture()
def llavero_b(kms: Any) -> TenantKeyRing:
    return TenantKeyRing(TENANT_B, environment=ENTORNO, region=REGION, client=kms)


def _digest(contenido: bytes = b"acta canonica de prueba") -> bytes:
    return hashlib.sha256(contenido).digest()


# ------------------------------------------------------------------- Alias ---
class TestSeleccionPorAlias:
    """Regla inviolable 9: la clave se nombra por alias versionado."""

    def test_el_alias_lleva_entorno_inquilino_y_version(self) -> None:
        alias = KeyAliases(tenant_id=TENANT_A, environment="prod", acta_seal_version=2)

        assert alias.acta_seal == f"alias/fnc/prod/{TENANT_A}/acta-seal/v2"
        assert alias.evidence == f"alias/fnc/prod/{TENANT_A}/evidence/v1"

    def test_dos_inquilinos_nunca_comparten_alias(self) -> None:
        a = KeyAliases(tenant_id=TENANT_A, environment=ENTORNO)
        b = KeyAliases(tenant_id=TENANT_B, environment=ENTORNO)

        assert a.acta_seal != b.acta_seal
        assert a.evidence != b.evidence

    def test_el_mismo_inquilino_en_otro_entorno_usa_otra_clave(self) -> None:
        """Las claves nunca se comparten entre entornos (ADR-0006)."""
        dev = KeyAliases(tenant_id=TENANT_A, environment="dev")
        prod = KeyAliases(tenant_id=TENANT_A, environment="prod")

        assert dev.acta_seal != prod.acta_seal

    def test_rechaza_un_identificador_de_inquilino_invalido(self) -> None:
        """Un identificador con barras construiría un alias con otra ruta."""
        for invalido in ("../otro-tenant", "tenant/con/barras", "a", ""):
            with pytest.raises(TenantKeyError, match="inválido"):
                KeyAliases(tenant_id=invalido, environment=ENTORNO)

    def test_el_llavero_expone_el_alias_que_usa(self, llavero_a: TenantKeyRing) -> None:
        """El alias viaja como `kid` del sobre JWS: tiene que ser consultable."""
        assert llavero_a.acta_seal_alias.endswith(f"{TENANT_A}/acta-seal/v1")


# ------------------------------------------------------------------ Sello ---
class TestSelladoDeActa:
    def test_sella_un_digest_y_devuelve_el_alias_usado(self, llavero_a: TenantKeyRing) -> None:
        resultado = llavero_a.seal(_digest())

        assert resultado.signature
        assert resultado.algorithm == ALGORITMO_SELLO
        assert resultado.key_alias == llavero_a.acta_seal_alias

    def test_rechaza_algo_que_no_sea_un_digest_sha256(self, llavero_a: TenantKeyRing) -> None:
        with pytest.raises(TenantKeyError, match="32 bytes"):
            llavero_a.seal(b"demasiado corto")

    def test_el_sello_se_verifica_con_la_clave_del_mismo_inquilino(
        self, llavero_a: TenantKeyRing, kms: Any
    ) -> None:
        digest = _digest()
        resultado = llavero_a.seal(digest)

        verificacion = kms.verify(
            KeyId=llavero_a.acta_seal_alias,
            Message=digest,
            MessageType="DIGEST",
            Signature=resultado.signature,
            SigningAlgorithm=ALGORITMO_SELLO,
        )

        assert verificacion["SignatureValid"] is True

    def test_cada_inquilino_publica_una_clave_publica_distinta(
        self, llavero_a: TenantKeyRing, llavero_b: TenantKeyRing
    ) -> None:
        """Sin esto, publicar la clave de un inquilino expondría la de todos."""
        assert llavero_a.public_key_der() != llavero_b.public_key_der()

    def test_un_alias_inexistente_falla_como_error_de_firma(self, kms: Any) -> None:
        huerfano = TenantKeyRing(
            "inquilino-sin-claves", environment=ENTORNO, region=REGION, client=kms
        )

        with pytest.raises(SigningError, match="sellar el acta"):
            huerfano.seal(_digest())


# ------------------------------------------- Aislamiento entre inquilinos ---
class TestAislamientoCriptografico:
    """Regla inviolable 7: una operación sobre A no alcanza la clave de B."""

    def test_cifra_y_descifra_dentro_del_mismo_contexto(self, llavero_a: TenantKeyRing) -> None:
        dato = b"numero de documento del firmante"

        cifrado = llavero_a.encrypt(dato, transaction_id=TX_A)

        assert llavero_a.decrypt(cifrado, transaction_id=TX_A) == dato

    def test_el_texto_cifrado_no_contiene_el_dato_en_claro(self, llavero_a: TenantKeyRing) -> None:
        dato = b"4829153"

        assert dato not in llavero_a.encrypt(dato, transaction_id=TX_A)

    def test_otro_inquilino_no_puede_descifrar(
        self, llavero_a: TenantKeyRing, llavero_b: TenantKeyRing
    ) -> None:
        """El caso que este diseño existe para impedir.

        Aunque el inquilino B tuviera el texto cifrado de A y permisos sobre su
        propia clave, el descifrado falla: son claves distintas y el contexto
        autenticado tampoco coincide.
        """
        cifrado = llavero_a.encrypt(b"dato reservado de A", transaction_id=TX_A)

        with pytest.raises(CrossTenantKeyAccessError):
            llavero_b.decrypt(cifrado, transaction_id=TX_A)

    def test_no_se_puede_descifrar_en_otra_transaccion(self, llavero_a: TenantKeyRing) -> None:
        """El contexto liga el dato a su transacción, no solo a su inquilino.

        Impide que la evidencia de un acto se reutilice como evidencia de otro.
        """
        cifrado = llavero_a.encrypt(b"dato de la transaccion A", transaction_id=TX_A)

        with pytest.raises(CrossTenantKeyAccessError):
            llavero_a.decrypt(cifrado, transaction_id=TX_B)

    def test_el_contexto_de_cifrado_lleva_inquilino_y_transaccion(
        self, llavero_a: TenantKeyRing
    ) -> None:
        """Regla inviolable 10, comprobada sobre el contexto mismo."""
        contexto = llavero_a.encryption_context(TX_A)

        assert contexto == {"tenant_id": TENANT_A, "transaction_id": TX_A}

    def test_sin_transaccion_no_hay_operacion(self, llavero_a: TenantKeyRing) -> None:
        """Una operación sin transacción no puede rastrearse hasta su acto."""
        with pytest.raises(TenantKeyError, match="identificador de la transacción"):
            llavero_a.encrypt(b"dato", transaction_id="")

    def test_el_sello_de_un_inquilino_no_valida_con_la_clave_de_otro(
        self, llavero_a: TenantKeyRing, llavero_b: TenantKeyRing, kms: Any
    ) -> None:
        """Un tercero no puede hacer pasar un acta de A por una de B.

        El rechazo se acepta en cualquiera de sus dos formas porque el simulador
        y el servicio real difieren: AWS lanza `KMSInvalidSignatureException` y
        `moto` devuelve `SignatureValid: False`. La prueba comprueba lo que
        importa —que la firma no se da por válida— y no la forma del rechazo, que
        es un detalle del proveedor.
        """
        digest = _digest()
        sello_de_a = llavero_a.seal(digest)

        try:
            resultado = kms.verify(
                KeyId=llavero_b.acta_seal_alias,
                Message=digest,
                MessageType="DIGEST",
                Signature=sello_de_a.signature,
                SigningAlgorithm=ALGORITMO_SELLO,
            )
        except kms.exceptions.KMSInvalidSignatureException:
            return  # Comportamiento de AWS: rechazo por excepción.

        assert resultado["SignatureValid"] is False
