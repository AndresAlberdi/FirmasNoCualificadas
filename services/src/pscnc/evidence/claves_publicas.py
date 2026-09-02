"""Publicación de las claves públicas de sello como un JWKS.

## Por qué se publica

El acta sellada solo sirve como prueba si un tercero puede verificarla **sin
pedirnos nada**. Un sello que solo nosotros sabemos comprobar no traslada
confianza: la concentra. Publicar la clave pública en el formato estándar (JWKS,
RFC 7517) permite que el inquilino, su asesoría legal o un perito verifiquen el
acta con cualquier librería JOSE, hoy y dentro de años.

## Qué se publica y qué no

Solo material **público**: las coordenadas de la clave pública de cada inquilino y
el `kid` que las identifica. Nunca la clave privada, que no puede salir del HSM ni
aunque quisiéramos, y nunca datos del inquilino más allá del identificador que ya
viaja en el acta.

Se publican **todas las versiones vigentes** de cada clave, no solo la última. Es
lo que hace posible una rotación sin invalidar el pasado: un acta sellada hace dos
años se verifica con la clave de entonces, que sigue publicada aunque ya no firme.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

from asn1crypto.keys import PublicKeyInfo

from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.logging_setup import get_logger

logger = get_logger(__name__)

#: Curva de la clave de sello, en la nomenclatura de JOSE (RFC 7518).
CURVA_JOSE = "P-256"

#: Longitud de cada coordenada en la curva P-256.
LONGITUD_COORDENADA = 32


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


@dataclass(frozen=True, slots=True)
class JsonWebKey:
    """Una clave pública en formato JWK (RFC 7517)."""

    kid: str
    x: str
    y: str
    kty: str = "EC"
    crv: str = CURVA_JOSE
    alg: str = "ES256"
    use: str = "sig"

    def to_dict(self) -> dict[str, str]:
        return {
            "kty": self.kty,
            "crv": self.crv,
            "alg": self.alg,
            "use": self.use,
            "kid": self.kid,
            "x": self.x,
            "y": self.y,
        }


def jwk_desde_der(public_key_der: bytes, *, kid: str) -> JsonWebKey:
    """Convierte la clave pública que devuelve KMS (DER) en un JWK.

    KMS entrega un `SubjectPublicKeyInfo`; JOSE espera las coordenadas `x` e `y`
    por separado, en base64url y rellenadas a la longitud de la curva. El punto
    viene en formato no comprimido: un byte `0x04` seguido de las dos coordenadas.
    """
    info = PublicKeyInfo.load(public_key_der)

    if info.algorithm != "ec":
        raise ValueError(f"Se esperaba una clave EC y se recibió {info.algorithm!r}")

    punto = bytes(info["public_key"].native)
    if not punto or punto[0] != 0x04:
        raise ValueError(
            "Se esperaba un punto EC en formato no comprimido (prefijo 0x04). "
            "Un punto comprimido exige derivar la coordenada y, y KMS no lo emite."
        )

    cuerpo = punto[1:]
    esperado = LONGITUD_COORDENADA * 2
    if len(cuerpo) != esperado:
        raise ValueError(f"El punto de una clave P-256 mide {esperado} bytes, no {len(cuerpo)}")

    return JsonWebKey(
        kid=kid,
        x=_b64url(cuerpo[:LONGITUD_COORDENADA]),
        y=_b64url(cuerpo[LONGITUD_COORDENADA:]),
    )


def construir_jwks(llaveros: list[TenantKeyRing]) -> dict[str, Any]:
    """Arma el documento JWKS con las claves de sello indicadas.

    Un llavero cuya clave no pueda leerse se omite y se registra, en lugar de
    hacer fallar el documento entero: dejar sin verificación a todos los
    inquilinos porque uno tiene un problema sería un fallo desproporcionado.
    """
    claves: list[dict[str, str]] = []

    for llavero in llaveros:
        try:
            jwk = jwk_desde_der(llavero.public_key_der(), kid=llavero.acta_seal_alias)
        except Exception as exc:
            logger.error(
                "jwks_key_unavailable",
                tenant_id=llavero.tenant_id,
                alias=llavero.acta_seal_alias,
                error=str(exc),
            )
            continue
        claves.append(jwk.to_dict())

    return {"keys": claves}
