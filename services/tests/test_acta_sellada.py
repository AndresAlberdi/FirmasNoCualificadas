"""Sellado del acta de evidencia (ADR-0006 §6, ADR-0007 nivel 1).

La prueba que sostiene todo el diseño es
`test_el_sello_se_verifica_con_una_libreria_ajena`: el acta se verifica con
`jwcrypto`, que no comparte una línea de código con el sellador. Verificar con el
mismo código que firma no demuestra interoperabilidad — demuestra que el código es
consistente consigo mismo, incluso cuando está equivocado. El caso concreto que
esa prueba atrapa es el formato de la firma: KMS devuelve ECDSA en DER y JWS exige
`R || S` en crudo, y un sobre con el DER dentro parece correcto y no lo acepta
ninguna librería estándar.

## Por qué estas pruebas no usan `moto`

`moto` **ignora `MessageType="DIGEST"`**: vuelve a aplicar SHA-256 sobre el digest
que se le envía, mientras que AWS firma ese digest tal cual. La diferencia importa
justamente acá, porque `ES256` exige una firma ECDSA sobre `SHA-256(signing
input)`: con la semántica de AWS el sobre verifica con cualquier librería JOSE, y
con la de `moto` no verifica con ninguna.

Se comprobó el comportamiento de ambos antes de decidir. Usar `moto` habría dado
una prueba en rojo por un defecto del simulador, y —peor— adaptar el código para
que `moto` la aceptara habría roto la interoperabilidad real. Por eso estas
pruebas usan `KmsFiel`, un doble mínimo que respeta la semántica documentada de
`kms:Sign`. El resto de la batería sigue usando `moto`, donde esa diferencia no
interviene.

Todos los datos son sintéticos.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

import boto3
import pytest
from jwcrypto import jwk as jose_jwk
from jwcrypto import jws as jose_jws
from moto import mock_aws

from conftest import KmsFiel
from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.evidence.acta import (
    ALGORITMO_JWS,
    VERSION_ACTA,
    ActaPayload,
    ActaSealer,
    DocumentReference,
    canonicalizar,
    der_a_jose,
    hash_canonico,
    jose_a_der,
    leer_cabecera,
)
from pscnc.evidence.claves_publicas import construir_jwks, jwk_desde_der

REGION = "us-east-1"
ENTORNO = "dev"
TENANT = "aseguradora-py"
OTRO_TENANT = "banco-py"
TX = "c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb"
CERRADO = datetime(2026, 9, 2, 14, 30, 0, tzinfo=UTC)
SELLADO = datetime(2026, 9, 2, 14, 31, 15, tzinfo=UTC)


@pytest.fixture(autouse=True)
def credenciales_simuladas() -> None:
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_DEFAULT_REGION", REGION)


def _crear_clave_de_sello(cliente: Any, tenant: str) -> None:
    clave = cliente.create_key(KeyUsage="SIGN_VERIFY", KeySpec="ECC_NIST_P256")["KeyMetadata"][
        "KeyId"
    ]
    cliente.create_alias(AliasName=f"alias/fnc/{ENTORNO}/{tenant}/acta-seal/v1", TargetKeyId=clave)


@pytest.fixture()
def kms() -> Any:
    """KMS con semántica fiel a AWS, no `moto` (ver la cabecera del módulo)."""
    return KmsFiel(
        [
            f"alias/fnc/{ENTORNO}/{TENANT}/acta-seal/v1",
            f"alias/fnc/{ENTORNO}/{OTRO_TENANT}/acta-seal/v1",
        ]
    )


@pytest.fixture()
def kms_moto() -> Any:
    """KMS simulado con `moto`, para lo que no depende de la semántica del digest."""
    with mock_aws():
        cliente = boto3.client("kms", region_name=REGION)
        _crear_clave_de_sello(cliente, TENANT)
        _crear_clave_de_sello(cliente, OTRO_TENANT)
        yield cliente


@pytest.fixture()
def llavero(kms: Any) -> TenantKeyRing:
    return TenantKeyRing(TENANT, environment=ENTORNO, region=REGION, client=kms)


@pytest.fixture()
def sellador(llavero: TenantKeyRing) -> ActaSealer:
    return ActaSealer(llavero)


def _acta(tenant: str = TENANT, nivel: int = 1) -> ActaPayload:
    return ActaPayload(
        tenant_id=tenant,
        transaction_id=TX,
        jurisdiction="PY",
        service_level=nivel,
        document=DocumentReference(
            sha256="a" * 64,
            version=2,
            code="PROP-2026-000123",
            closed_at=CERRADO,
        ),
        evidence_sha256="b" * 64,
        tenant_reference="EXP-99887",
    )


# ------------------------------------------------------- Canonicalización ---
class TestCanonicalizacion:
    def test_el_orden_de_las_claves_no_altera_el_resultado(self) -> None:
        """La propiedad que hace que «el mismo contenido» sean «los mismos bytes»."""
        uno = {"b": 1, "a": {"z": 2, "y": 3}}
        otro = {"a": {"y": 3, "z": 2}, "b": 1}

        assert canonicalizar(uno) == canonicalizar(otro)

    def test_el_hash_es_estable_entre_serializaciones(self) -> None:
        acta = _acta()

        primero = hash_canonico(acta.to_payload(sealed_at=SELLADO))
        segundo = hash_canonico(acta.to_payload(sealed_at=SELLADO))

        assert primero == segundo

    def test_un_cambio_minimo_cambia_el_hash(self) -> None:
        base = _acta().to_payload(sealed_at=SELLADO)
        alterado = _acta().to_payload(sealed_at=SELLADO)
        alterado["document"]["version"] = 3

        assert hash_canonico(base) != hash_canonico(alterado)

    def test_el_instante_se_normaliza_sin_microsegundos(self) -> None:
        """Dos representaciones del mismo instante darían hashes distintos."""
        con_micros = _acta().to_payload(
            sealed_at=datetime(2026, 9, 2, 14, 31, 15, 123456, tzinfo=UTC)
        )

        assert con_micros["sealed_at"] == "2026-09-02T14:31:15Z"

    def test_un_instante_sin_zona_se_interpreta_como_utc(self) -> None:
        payload = _acta().to_payload(sealed_at=datetime(2026, 9, 2, 14, 31, 15))

        assert payload["sealed_at"].endswith("Z")


# ------------------------------------------------- Formato de la firma ------
class TestFormatoDeFirma:
    """El detalle que rompe la interoperabilidad si se pasa por alto."""

    def test_la_firma_jose_mide_sesenta_y_cuatro_bytes(self, llavero: TenantKeyRing) -> None:
        import hashlib

        firma_der = llavero.seal(hashlib.sha256(b"algo").digest()).signature

        assert len(der_a_jose(firma_der)) == 64

    def test_la_conversion_es_reversible(self, llavero: TenantKeyRing) -> None:
        import hashlib

        firma_der = llavero.seal(hashlib.sha256(b"algo").digest()).signature

        assert jose_a_der(der_a_jose(firma_der)) == firma_der

    def test_rechaza_una_firma_jose_de_longitud_incorrecta(self) -> None:
        with pytest.raises(ValueError, match="64 bytes"):
            jose_a_der(b"\x00" * 63)

    def test_el_der_de_kms_no_sirve_tal_cual(self, llavero: TenantKeyRing) -> None:
        """Deja constancia de por qué la conversión existe.

        El DER es más largo que 64 bytes y lleva estructura ASN.1: usarlo como
        firma JOSE produce un sobre que ninguna librería estándar acepta.
        """
        import hashlib

        firma_der = llavero.seal(hashlib.sha256(b"algo").digest()).signature

        assert len(firma_der) != 64
        assert firma_der[0] == 0x30  # SEQUENCE


# -------------------------------------------------------------- Sellado ----
class TestSellado:
    def test_el_sobre_tiene_tres_partes(self, sellador: ActaSealer) -> None:
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        assert len(sellada.jws.split(".")) == 3

    def test_la_cabecera_declara_algoritmo_y_clave(self, sellador: ActaSealer) -> None:
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        cabecera = leer_cabecera(sellada.jws)

        assert cabecera["alg"] == ALGORITMO_JWS
        assert cabecera["kid"] == sellada.key_alias
        assert cabecera["kid"].endswith(f"{TENANT}/acta-seal/v1")

    def test_el_acta_declara_su_version_de_formato(self, sellador: ActaSealer) -> None:
        """Un verificador que reciba una versión desconocida debe rechazarla."""
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        assert sellada.payload["acta_version"] == VERSION_ACTA

    def test_el_acta_declara_el_nivel_de_servicio(self, sellador: ActaSealer) -> None:
        """Un nivel 1 no sella los bytes del documento; el acta tiene que decirlo."""
        nivel_1 = sellador.seal(_acta(nivel=1), sealed_at=SELLADO)
        nivel_2 = sellador.seal(_acta(nivel=2), sealed_at=SELLADO)

        assert nivel_1.payload["service_level"] == 1
        assert nivel_2.payload["service_level"] == 2

    def test_el_acta_cita_el_expediente_del_inquilino(self, sellador: ActaSealer) -> None:
        """El registro del inquilino es el autoritativo; se citan mutuamente (ADR-0009)."""
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        assert sellada.payload["tenant_reference"] == "EXP-99887"
        assert sellada.payload["transaction_id"] == TX

    def test_los_campos_opcionales_ausentes_no_viajan_vacios(self, sellador: ActaSealer) -> None:
        """Un campo presente y vacío es indistinguible de un dato que se perdió."""
        sin_tsa = sellador.seal(_acta(), sealed_at=SELLADO)

        assert "timestamp" not in sin_tsa.payload

    def test_el_acta_no_contiene_datos_personales(self, sellador: ActaSealer) -> None:
        """El acta puede llegar a un juzgado y al inquilino: lleva huellas, no personas."""
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)
        texto = json.dumps(sellada.payload).lower()

        for prohibido in ("nombre", "apellido", "cedula", "national_id", "otp", "salud"):
            assert prohibido not in texto

    def test_no_se_puede_sellar_el_acta_de_otro_inquilino(self, sellador: ActaSealer) -> None:
        """El error aparecería recién en manos del tercero que intenta verificar."""
        with pytest.raises(ValueError, match="pertenece al inquilino"):
            sellador.seal(_acta(tenant=OTRO_TENANT), sealed_at=SELLADO)

    def test_el_hash_publicado_corresponde_al_contenido_sellado(self, sellador: ActaSealer) -> None:
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        assert sellada.payload_sha256 == hash_canonico(sellada.payload)

    def test_un_sobre_mal_formado_se_rechaza_al_leer_la_cabecera(self) -> None:
        with pytest.raises(ValueError, match="tres partes"):
            leer_cabecera("esto.no-es-un-jws")


# --------------------------------------- Verificación con librería ajena ----
class TestVerificacionInteroperable:
    """El corazón de la fase: que el acta sirva sin nuestro código."""

    def _clave_publica_jose(self, llavero: TenantKeyRing) -> jose_jwk.JWK:
        jwk = jwk_desde_der(llavero.public_key_der(), kid=llavero.acta_seal_alias)
        return jose_jwk.JWK(**jwk.to_dict())

    def test_el_sello_se_verifica_con_una_libreria_ajena(
        self, sellador: ActaSealer, llavero: TenantKeyRing
    ) -> None:
        """Verificar con el mismo código que firma no demuestra interoperabilidad."""
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)

        verificador = jose_jws.JWS()
        verificador.deserialize(sellada.jws)
        verificador.verify(self._clave_publica_jose(llavero))

        recuperado = json.loads(verificador.payload)
        assert recuperado["transaction_id"] == TX
        assert recuperado["document"]["sha256"] == "a" * 64

    def test_un_acta_alterada_no_verifica(
        self, sellador: ActaSealer, llavero: TenantKeyRing
    ) -> None:
        """La propiedad que hace del acta una prueba y no una declaración."""
        import base64

        sellada = sellador.seal(_acta(), sealed_at=SELLADO)
        cabecera, payload, firma = sellada.jws.split(".")

        adulterado = json.loads(base64.urlsafe_b64decode(payload + "=="))
        adulterado["document"]["sha256"] = "f" * 64
        payload_falso = base64.urlsafe_b64encode(canonicalizar(adulterado)).decode().rstrip("=")

        verificador = jose_jws.JWS()
        verificador.deserialize(f"{cabecera}.{payload_falso}.{firma}")

        with pytest.raises(jose_jws.InvalidJWSSignature):
            verificador.verify(self._clave_publica_jose(llavero))

    def test_la_clave_de_otro_inquilino_no_verifica(self, sellador: ActaSealer, kms: Any) -> None:
        """Un acta de un inquilino no puede hacerse pasar por la de otro."""
        sellada = sellador.seal(_acta(), sealed_at=SELLADO)
        ajeno = TenantKeyRing(OTRO_TENANT, environment=ENTORNO, region=REGION, client=kms)

        verificador = jose_jws.JWS()
        verificador.deserialize(sellada.jws)

        with pytest.raises(jose_jws.InvalidJWSSignature):
            verificador.verify(self._clave_publica_jose(ajeno))


# ------------------------------------------------- Publicación de claves ----
class TestClavesPublicas:
    def test_el_jwks_lleva_las_claves_de_cada_inquilino(self, kms: Any) -> None:
        llaveros = [
            TenantKeyRing(TENANT, environment=ENTORNO, region=REGION, client=kms),
            TenantKeyRing(OTRO_TENANT, environment=ENTORNO, region=REGION, client=kms),
        ]

        jwks = construir_jwks(llaveros)

        assert len(jwks["keys"]) == 2
        assert {k["kid"] for k in jwks["keys"]} == {llavero.acta_seal_alias for llavero in llaveros}

    def test_el_jwks_declara_curva_y_uso(self, llavero: TenantKeyRing) -> None:
        clave = construir_jwks([llavero])["keys"][0]

        assert clave["kty"] == "EC"
        assert clave["crv"] == "P-256"
        assert clave["alg"] == "ES256"
        assert clave["use"] == "sig"

    def test_el_jwks_no_expone_material_privado(self, llavero: TenantKeyRing) -> None:
        """La clave privada no puede salir del HSM; el documento tampoco debe sugerirlo."""
        clave = construir_jwks([llavero])["keys"][0]

        for privado in ("d", "p", "q", "dp", "dq", "qi", "k"):
            assert privado not in clave

    def test_un_inquilino_sin_clave_no_rompe_el_documento(self, kms: Any) -> None:
        """Dejar sin verificación a todos porque uno falla sería desproporcionado."""
        sano = TenantKeyRing(TENANT, environment=ENTORNO, region=REGION, client=kms)
        roto = TenantKeyRing("inquilino-sin-claves", environment=ENTORNO, region=REGION, client=kms)

        jwks = construir_jwks([sano, roto])

        assert len(jwks["keys"]) == 1
        assert jwks["keys"][0]["kid"] == sano.acta_seal_alias

    def test_rechaza_una_clave_que_no_sea_eliptica(self, kms_moto: Any) -> None:
        rsa = kms_moto.create_key(KeyUsage="SIGN_VERIFY", KeySpec="RSA_2048")["KeyMetadata"][
            "KeyId"
        ]
        publica = kms_moto.get_public_key(KeyId=rsa)["PublicKey"]

        with pytest.raises(ValueError, match="clave EC"):
            jwk_desde_der(publica, kid="alias/de/prueba")
