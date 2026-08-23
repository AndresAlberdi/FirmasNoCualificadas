"""Pruebas de la autenticación HMAC de las peticiones B2B."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from pscnc.errors import AuthenticationError, TenantMismatchError
from pscnc.orchestrator.security import (
    HEADER_CLIENT,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    StaticSecretResolver,
    authenticate,
    sign_request,
)
from pscnc.repositories.dynamo_audit import SecurityContext

SECRETO = b"secreto-de-pruebas"
CLIENTE = "aseguradora-py"
RUTA = "/v1/signing-sessions"
CUERPO = b'{"onboarding_token":"abc"}'


def _resolver() -> StaticSecretResolver:
    return StaticSecretResolver(secrets={CLIENTE: SECRETO})


def _cabeceras(*, momento: datetime | None = None, cuerpo: bytes = CUERPO) -> dict[str, str]:
    instante = (momento or datetime.now(UTC)).isoformat()
    return {
        HEADER_CLIENT: CLIENTE,
        HEADER_TIMESTAMP: instante,
        HEADER_SIGNATURE: sign_request(SECRETO, "POST", RUTA, instante, cuerpo),
    }


def test_autenticacion_valida_devuelve_contexto_del_inquilino() -> None:
    contexto = authenticate(
        headers=_cabeceras(),
        method="POST",
        path=RUTA,
        body=CUERPO,
        resolver=_resolver(),
    )
    assert contexto.b2b_client_id == CLIENTE


def test_rechaza_cuerpo_alterado() -> None:
    """La firma cubre el cuerpo: cualquier modificación invalida la petición."""
    cabeceras = _cabeceras()
    with pytest.raises(AuthenticationError, match="Firma"):
        authenticate(
            headers=cabeceras,
            method="POST",
            path=RUTA,
            body=b'{"onboarding_token":"OTRO"}',
            resolver=_resolver(),
        )


def test_rechaza_ruta_distinta() -> None:
    with pytest.raises(AuthenticationError):
        authenticate(
            headers=_cabeceras(),
            method="POST",
            path="/v1/otra-ruta",
            body=CUERPO,
            resolver=_resolver(),
        )


def test_rechaza_peticion_fuera_de_ventana() -> None:
    """Limita la ventana de reutilización de una petición capturada."""
    antigua = datetime.now(UTC) - timedelta(minutes=30)
    with pytest.raises(AuthenticationError, match="ventana temporal"):
        authenticate(
            headers=_cabeceras(momento=antigua),
            method="POST",
            path=RUTA,
            body=CUERPO,
            resolver=_resolver(),
            max_skew_seconds=300,
        )


def test_rechaza_cliente_desconocido() -> None:
    cabeceras = _cabeceras()
    cabeceras[HEADER_CLIENT] = "cliente-inexistente"
    with pytest.raises(AuthenticationError, match="Credenciales"):
        authenticate(
            headers=cabeceras,
            method="POST",
            path=RUTA,
            body=CUERPO,
            resolver=_resolver(),
        )


def test_rechaza_falta_de_cabeceras() -> None:
    with pytest.raises(AuthenticationError, match="cabeceras"):
        authenticate(
            headers={HEADER_CLIENT: CLIENTE},
            method="POST",
            path=RUTA,
            body=CUERPO,
            resolver=_resolver(),
        )


def test_contexto_bloquea_acceso_cruzado_entre_inquilinos() -> None:
    """Verificación estructural del ADR-0005."""
    contexto = SecurityContext(b2b_client_id="banco-a")
    contexto.assert_owns("banco-a")
    with pytest.raises(TenantMismatchError):
        contexto.assert_owns("banco-b")
