"""Acta de evidencia sellada: el artefacto verificable del nivel 1 (ADR-0006, ADR-0007).

## Qué es y por qué existe

En el nivel 1 el documento no se modifica: el PDF firmado es byte a byte el que se
cerró. Lo que prueba el acto de firma es el **registro**, y un registro que
nosotros mismos podemos reescribir no prueba nada. El acta sellada cierra ese
hueco: es un resumen de lo ocurrido, firmado con la clave del inquilino en KMS,
que un tercero puede verificar con la clave pública publicada **sin acceso a
nuestros sistemas y sin tener que confiar en nosotros**.

## Dos decisiones de formato, y qué pasa si se ignoran

**JSON canónico (RFC 8785).** Sin un orden de claves determinista y una
representación fija de los números, dos serializaciones del mismo acta producen
hashes distintos, y la verificación falla por motivos que nada tienen que ver con
la integridad. La canonicalización no es un detalle estético: es lo que hace que
«el mismo contenido» signifique «los mismos bytes».

**Sobre JWS con `kid` igual al alias versionado.** El inquilino verifica con
cualquier librería JOSE estándar, sin código nuestro. El `kid` le dice cuál de las
claves publicadas usar, que es exactamente lo que hace falta durante una rotación,
cuando conviven dos versiones — la anterior verificando y la nueva firmando.

## El detalle que rompe la interoperabilidad si se pasa por alto

KMS devuelve las firmas ECDSA en **DER** (una secuencia ASN.1 con los enteros `r`
y `s`). JWS `ES256` exige los dos enteros **en crudo, concatenados y rellenados a
32 bytes cada uno** (RFC 7518 §3.4). Entregar el DER tal cual produce un sobre que
parece correcto, que nuestro propio código verificaría si compartiera el error, y
que **ninguna librería estándar acepta**. La conversión vive acá, con su prueba.
"""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import rfc8785
from cryptography.hazmat.primitives.asymmetric.utils import (
    decode_dss_signature,
    encode_dss_signature,
)

from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

#: Algoritmo JOSE del sello. Se corresponde con `ECDSA_SHA_256` de KMS.
ALGORITMO_JWS = "ES256"

#: Longitud de cada entero de una firma ECDSA sobre la curva P-256.
LONGITUD_COORDENADA = 32

#: Versión del formato del acta. Un verificador que reciba una versión que no
#: conoce debe rechazarla en lugar de interpretarla a medias.
VERSION_ACTA = 1


def der_a_jose(firma_der: bytes) -> bytes:
    """Convierte una firma ECDSA de DER a la forma cruda que exige JOSE.

    RFC 7518 §3.4: `ES256` transporta `R || S`, cada uno rellenado con ceros a la
    izquierda hasta 32 bytes. El DER, en cambio, codifica enteros de longitud
    variable y puede llevar un byte de relleno para forzar el signo positivo.

    Se usan las funciones de `cryptography` en lugar de analizar la secuencia
    ASN.1 a mano: son la implementación de referencia de esta conversión y evitan
    reimplementar un caso de borde —el relleno de signo— que es fácil de pasar por
    alto y produce firmas inválidas solo en algunas de cada cientos.
    """
    r, s = decode_dss_signature(firma_der)
    return r.to_bytes(LONGITUD_COORDENADA, "big") + s.to_bytes(LONGITUD_COORDENADA, "big")


def jose_a_der(firma_jose: bytes) -> bytes:
    """Inversa de `der_a_jose`, para verificar contra KMS un sello ya emitido."""
    if len(firma_jose) != LONGITUD_COORDENADA * 2:
        raise ValueError(
            f"Una firma ES256 mide {LONGITUD_COORDENADA * 2} bytes, no {len(firma_jose)}"
        )
    r = int.from_bytes(firma_jose[:LONGITUD_COORDENADA], "big")
    s = int.from_bytes(firma_jose[LONGITUD_COORDENADA:], "big")
    return bytes(encode_dss_signature(r, s))


def b64url(datos: bytes) -> str:
    """Base64url sin relleno, como exige JOSE."""
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def desde_b64url(texto: str) -> bytes:
    relleno = "=" * (-len(texto) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def canonicalizar(payload: dict[str, Any]) -> bytes:
    """Serializa el acta en JSON canónico (RFC 8785)."""
    return bytes(rfc8785.dumps(payload))


def hash_canonico(payload: dict[str, Any]) -> str:
    """SHA-256 hexadecimal del acta canonicalizada."""
    return hashlib.sha256(canonicalizar(payload)).hexdigest()


@dataclass(frozen=True, slots=True)
class DocumentReference:
    """El documento sobre el que se firmó, identificado sin exponerlo.

    La versión viaja junto a la huella porque una huella suelta no dice contra qué
    comparar: si el documento se regenera, su huella cambia y sin la versión no
    hay forma de saber cuál de las dos es la que se firmó.
    """

    sha256: str
    version: int
    code: str
    closed_at: datetime


@dataclass(frozen=True, slots=True)
class ActaPayload:
    """Contenido del acta, antes de sellarse.

    Todos los campos son públicos por diseño: el acta se entrega al inquilino y
    puede llegar a un juzgado. **No contiene datos personales** — ni cédula, ni
    nombre, ni el código del OTP, ni nada de salud. Lo que contiene son huellas y
    referencias, que es lo que hace falta para probar integridad y trazabilidad
    sin difundir lo que se firmó.
    """

    tenant_id: str
    transaction_id: str
    jurisdiction: str
    service_level: int
    document: DocumentReference
    evidence_sha256: str
    #: Referencia del expediente en el sistema del inquilino, que es el registro
    #: autoritativo del contrato (ADR-0009). El acta y aquel se citan mutuamente.
    tenant_reference: str = ""
    #: Token RFC 3161, si la transacción llegó a tener sello de tiempo.
    timestamp_token_sha256: str = ""
    #: Autoridad que emitió ese token.
    timestamp_authority: str = ""

    def to_payload(self, *, sealed_at: datetime) -> dict[str, Any]:
        """Construye el diccionario que se canonicaliza y se sella."""
        payload: dict[str, Any] = {
            "acta_version": VERSION_ACTA,
            "tenant_id": self.tenant_id,
            "transaction_id": self.transaction_id,
            "jurisdiction": self.jurisdiction,
            "service_level": self.service_level,
            "document": {
                "sha256": self.document.sha256,
                "version": self.document.version,
                "code": self.document.code,
                "closed_at": _instante(self.document.closed_at),
            },
            "evidence_sha256": self.evidence_sha256,
            "sealed_at": _instante(sealed_at),
        }
        # Los campos opcionales se omiten en lugar de viajar vacíos: un campo
        # presente y vacío es indistinguible de un dato que se perdió.
        if self.tenant_reference:
            payload["tenant_reference"] = self.tenant_reference
        if self.timestamp_token_sha256:
            payload["timestamp"] = {
                "token_sha256": self.timestamp_token_sha256,
                "authority": self.timestamp_authority,
            }
        return payload


def _instante(valor: datetime) -> str:
    """Instante en ISO-8601 UTC, con `Z` y sin microsegundos.

    La forma se fija acá y no en cada llamador: dos representaciones del mismo
    instante darían hashes distintos y romperían la verificación.
    """
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=UTC)
    return valor.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SealedActa:
    """Acta sellada, lista para entregarse."""

    #: Sobre JWS compacto: `header.payload.signature`.
    jws: str
    #: El contenido, para que el consumidor no tenga que decodificar el sobre.
    payload: dict[str, Any]
    #: SHA-256 del acta canonicalizada. Es lo que se firmó.
    payload_sha256: str
    #: Alias versionado de la clave, igual al `kid` del sobre.
    key_alias: str


class ActaSealer:
    """Sella actas de evidencia con la clave del inquilino."""

    def __init__(self, key_ring: TenantKeyRing) -> None:
        self._keys = key_ring

    def seal(self, acta: ActaPayload, *, sealed_at: datetime | None = None) -> SealedActa:
        """Canonicaliza, firma y arma el sobre JWS.

        Se comprueba que el acta corresponda al inquilino del llavero: sellar el
        acta de un inquilino con la clave de otro produciría un artefacto que no
        verifica con la clave pública que se le publicó, y el error aparecería
        recién en manos del tercero que intenta comprobarlo.
        """
        if acta.tenant_id != self._keys.tenant_id:
            raise ValueError(
                f"El acta pertenece al inquilino {acta.tenant_id!r} y el llavero "
                f"es de {self._keys.tenant_id!r}."
            )

        payload = acta.to_payload(sealed_at=sealed_at or datetime.now(UTC))
        payload_canonico = canonicalizar(payload)

        cabecera = {
            "alg": ALGORITMO_JWS,
            "typ": "JOSE",
            # El alias versionado: le dice al verificador cuál de las claves
            # publicadas usar, que es lo que hace falta durante una rotación.
            "kid": self._keys.acta_seal_alias,
        }
        cabecera_b64 = b64url(canonicalizar(cabecera))
        payload_b64 = b64url(payload_canonico)

        entrada_firma = f"{cabecera_b64}.{payload_b64}".encode("ascii")
        digest = hashlib.sha256(entrada_firma).digest()

        resultado = self._keys.seal(digest)
        firma_jose = der_a_jose(resultado.signature)

        jws = f"{cabecera_b64}.{payload_b64}.{b64url(firma_jose)}"

        logger.info(
            "acta_sealed_envelope",
            tenant_id=acta.tenant_id,
            transaction_id=acta.transaction_id,
            key_alias=resultado.key_alias,
            service_level=acta.service_level,
        )

        return SealedActa(
            jws=jws,
            payload=payload,
            payload_sha256=hashlib.sha256(payload_canonico).hexdigest(),
            key_alias=resultado.key_alias,
        )


def leer_cabecera(jws: str) -> dict[str, Any]:
    """Lee la cabecera de un sobre sin verificarlo.

    Sirve para saber con qué clave hay que verificar. **No valida nada**: el
    contenido de un sobre sin verificar es una afirmación de quien lo envió.
    """
    import json

    partes = jws.split(".")
    if len(partes) != 3:
        raise ValueError("Un sobre JWS compacto tiene tres partes separadas por puntos")
    cabecera: dict[str, Any] = json.loads(desde_b64url(partes[0]))
    return cabecera
