"""Pruebas de la superficie HTTP de la API B2B.

`test_security.py` ejercita la función de autenticación de forma aislada y
`test_signing_flow.py` el servicio de firma; ninguna de las dos recorre la
aplicación FastAPI. Estas pruebas cubren esa capa: el cableado de las
dependencias, la traducción de errores de dominio a códigos HTTP y la captura
del contexto de red con valor pericial.

Todos los datos son sintéticos (ver CONTRIBUTING.md).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from pscnc.errors import (
    LegallyExcludedDocumentError,
    SigningSessionNotFoundError,
    TenantMismatchError,
)
from pscnc.models.audit_trail import SigningStatus
from pscnc.orchestrator import app as modulo_app
from pscnc.orchestrator.app import IP_NO_CAPTURADA, app, entorno_de_peticion
from pscnc.orchestrator.security import (
    HEADER_CLIENT,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    StaticSecretResolver,
    sign_request,
)

SECRETO = b"secreto-de-pruebas"
CLIENTE = "aseguradora-py"
TX = "c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb"
PDF = b"%PDF-1.7\n% documento sintetico de prueba\n"


class ServicioFalso:
    """Doble del servicio de firma: registra las llamadas y devuelve lo que se le indique."""

    def __init__(self) -> None:
        self.llamadas: list[tuple[str, dict[str, Any]]] = []
        self.error: Exception | None = None

    def _quizas_fallar(self) -> None:
        if self.error is not None:
            raise self.error

    def create_session(self, **kwargs: Any) -> Any:
        self.llamadas.append(("create_session", kwargs))
        self._quizas_fallar()
        ahora = datetime.now(UTC)
        return {
            "signing_session_id": TX,
            "status": SigningStatus.INITIALIZED,
            "original_document_hash": "a" * 64,
            "created_at": ahora,
            "expires_at": ahora + timedelta(minutes=60),
        }

    def confirm(self, **kwargs: Any) -> Any:
        self.llamadas.append(("confirm", kwargs))
        self._quizas_fallar()
        return {
            "signing_session_id": TX,
            "status": SigningStatus.SIGNING_COMPLETED,
            "signed_document_hash": "b" * 64,
            "user_certificate_serial": "12345",
            "signature_format": "PAdES-B-T",
            "timestamp": {
                "authority": "TSA de prueba",
                "serial": "999",
                "time": datetime.now(UTC),
            },
        }

    def evidence(self, **kwargs: Any) -> Any:
        self.llamadas.append(("evidence", kwargs))
        self._quizas_fallar()
        return {
            "signing_session_id": TX,
            "status": SigningStatus.SIGNING_COMPLETED,
            "signed_document_url": "https://ejemplo.invalid/firmado.pdf",
            "evidence_report_url": "https://ejemplo.invalid/evidencias.pdf",
            "url_expires_in_seconds": 300,
            "original_document_hash": "a" * 64,
            "signed_document_hash": "b" * 64,
            "verifications": {
                "aml_pep_checked": True,
                "biometric_score": 0.985,
                "liveness_detected": True,
                "identity_match_approved": True,
            },
        }


@pytest.fixture()
def servicio(monkeypatch: pytest.MonkeyPatch) -> ServicioFalso:
    doble = ServicioFalso()
    monkeypatch.setattr(modulo_app, "build_signing_service", lambda: doble)
    monkeypatch.setattr(
        modulo_app, "get_secret_resolver", lambda: StaticSecretResolver({CLIENTE: SECRETO})
    )
    return doble


@pytest.fixture()
def cliente() -> Any:
    with TestClient(app) as c:
        yield c


def _firmar(metodo: str, ruta: str, cuerpo: bytes) -> dict[str, str]:
    instante = datetime.now(UTC).isoformat()
    return {
        HEADER_CLIENT: CLIENTE,
        HEADER_TIMESTAMP: instante,
        HEADER_SIGNATURE: sign_request(SECRETO, metodo, ruta, instante, cuerpo),
    }


# --------------------------------------------------------------- Operación ---
def test_health_no_exige_autenticacion(cliente) -> None:  # type: ignore[no-untyped-def]
    """La sonda del balanceador no puede depender de credenciales."""
    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


def test_health_no_revela_configuracion_sensible(cliente) -> None:  # type: ignore[no-untyped-def]
    cuerpo = respuesta_json = cliente.get("/health").json()

    assert set(respuesta_json) == {"status", "environment", "version", "crypto_backend"}
    assert "kms" not in str(cuerpo).lower() or cuerpo["crypto_backend"] in ("kms", "local")


# ---------------------------------------------------------- Autenticación ----
def test_rechaza_peticion_sin_firma(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    respuesta = cliente.get(f"/v1/signing-sessions/{TX}/evidence")

    assert respuesta.status_code == 401
    assert respuesta.json()["error"]["code"] == "unauthenticated"
    assert servicio.llamadas == []


def test_rechaza_firma_de_otro_secreto(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    ruta = f"/v1/signing-sessions/{TX}/evidence"
    instante = datetime.now(UTC).isoformat()
    cabeceras = {
        HEADER_CLIENT: CLIENTE,
        HEADER_TIMESTAMP: instante,
        HEADER_SIGNATURE: sign_request(b"otro-secreto", "GET", ruta, instante, b""),
    }

    respuesta = cliente.get(ruta, headers=cabeceras)

    assert respuesta.status_code == 401
    assert servicio.llamadas == []


def test_el_inquilino_sale_de_la_credencial_y_no_del_cuerpo(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    """Regla inviolable 6: el `b2b_client_id` nunca se toma de la petición."""
    ruta = f"/v1/signing-sessions/{TX}/evidence"
    cliente.get(ruta, headers=_firmar("GET", ruta, b""))

    _, kwargs = servicio.llamadas[0]
    assert kwargs["context"].b2b_client_id == CLIENTE


# ------------------------------------------------------------- Evidencia -----
def test_devuelve_el_paquete_de_evidencias(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    ruta = f"/v1/signing-sessions/{TX}/evidence"

    respuesta = cliente.get(ruta, headers=_firmar("GET", ruta, b""))

    assert respuesta.status_code == 200
    assert respuesta.json()["url_expires_in_seconds"] == 300


def test_transaccion_inexistente_devuelve_404(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    servicio.error = SigningSessionNotFoundError("No existe la sesión de firma solicitada")
    ruta = f"/v1/signing-sessions/{TX}/evidence"

    respuesta = cliente.get(ruta, headers=_firmar("GET", ruta, b""))

    assert respuesta.status_code == 404
    assert respuesta.json()["error"]["code"] == "signing_session_not_found"


def test_acceso_cruzado_entre_inquilinos_devuelve_403(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    servicio.error = TenantMismatchError("El recurso solicitado pertenece a otro cliente B2B")
    ruta = f"/v1/signing-sessions/{TX}/evidence"

    respuesta = cliente.get(ruta, headers=_firmar("GET", ruta, b""))

    assert respuesta.status_code == 403
    assert respuesta.json()["error"]["code"] == "tenant_mismatch"


# ----------------------------------------------------------- Crear sesión ----
def _crear_sesion(cliente: Any, *, pdf: bytes = PDF, metadata: str | None = None) -> Any:
    ruta = "/v1/signing-sessions"
    datos: dict[str, str] = {"onboarding_token": "onb-pruebas"}
    if metadata is not None:
        datos["metadata"] = metadata
    archivos = {"pdf_document": ("contrato.pdf", pdf, "application/pdf")}

    # La firma HMAC cubre el cuerpo, y en multipart lo construye httpx con un
    # `boundary` aleatorio. Se arma una petición para materializar esos bytes,
    # se firman, y se envía una petición nueva con el mismo cuerpo y el mismo
    # `content-type`: reutilizar la primera fallaría, porque leerla consume su
    # stream.
    plantilla = cliente.build_request("POST", ruta, data=datos, files=archivos)
    cuerpo = plantilla.read()

    cabeceras = _firmar("POST", ruta, cuerpo)
    cabeceras["content-type"] = plantilla.headers["content-type"]
    return cliente.post(ruta, content=cuerpo, headers=cabeceras)


def test_crea_la_sesion_de_firma(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    respuesta = _crear_sesion(cliente)

    assert respuesta.status_code == 201
    assert respuesta.json()["status"] == "INITIALIZED"
    assert servicio.llamadas[0][0] == "create_session"


def test_rechaza_un_documento_que_supera_el_maximo(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    """El límite protege la memoria del contenedor de firma."""
    respuesta = _crear_sesion(cliente, pdf=b"%PDF-1.7" + b"\x00" * (25 * 1024 * 1024))

    assert respuesta.status_code == 500
    assert "25 MiB" in respuesta.json()["error"]["message"]


def test_rechaza_metadata_que_no_sea_json(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    respuesta = _crear_sesion(cliente, metadata="esto no es json")

    assert respuesta.status_code == 500
    assert "metadata" in respuesta.json()["error"]["message"]


def test_acto_juridico_excluido_devuelve_403(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    servicio.error = LegallyExcludedDocumentError(
        "El documento contiene indicios de un acto jurídico excluido",
        detail={"blocking_terms": ["hipoteca"]},
    )

    respuesta = _crear_sesion(cliente)

    assert respuesta.status_code == 403
    cuerpo = respuesta.json()["error"]
    assert cuerpo["code"] == "legally_excluded_document"
    assert cuerpo["blocking_terms"] == ["hipoteca"]


# --------------------------------------------------------------- Confirmar ---
def test_confirma_la_firma(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    import json

    ruta = f"/v1/signing-sessions/{TX}/confirm"
    cuerpo = json.dumps(
        {"consent_otp_code": "123456", "consent_statement": "Acepto firmar el documento."}
    ).encode()

    respuesta = cliente.post(
        ruta,
        content=cuerpo,
        headers={**_firmar("POST", ruta, cuerpo), "content-type": "application/json"},
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["signature_format"] == "PAdES-B-T"


def test_el_codigo_otp_no_vuelve_en_la_respuesta(cliente, servicio) -> None:  # type: ignore[no-untyped-def]
    """Regla inviolable 1: el código no aparece en ninguna salida."""
    import json

    ruta = f"/v1/signing-sessions/{TX}/confirm"
    cuerpo = json.dumps(
        {"consent_otp_code": "654321", "consent_statement": "Acepto firmar el documento."}
    ).encode()

    respuesta = cliente.post(
        ruta,
        content=cuerpo,
        headers={**_firmar("POST", ruta, cuerpo), "content-type": "application/json"},
    )

    assert "654321" not in respuesta.text


# ------------------------------------------------- Contexto de red pericial --
class _PeticionFalsa:
    def __init__(self, headers: dict[str, str], client: Any) -> None:
        self.headers = headers
        self.client = client


class _Cliente:
    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port


def test_la_ip_se_toma_del_primer_salto_de_x_forwarded_for() -> None:
    """Detrás del balanceador, el cliente real es el primer elemento de la cadena."""
    entorno = entorno_de_peticion(
        _PeticionFalsa(  # type: ignore[arg-type]
            {"x-forwarded-for": "190.104.128.5, 10.0.0.7", "user-agent": "navegador"},
            _Cliente("10.0.0.7", 45000),
        )
    )

    assert entorno.client_ip == "190.104.128.5"


def test_sin_direccion_determinable_se_marca_explicitamente() -> None:
    """Escribir `0.0.0.0` haría indistinguible el dato de su ausencia."""
    entorno = entorno_de_peticion(_PeticionFalsa({}, None))  # type: ignore[arg-type]

    assert entorno.client_ip == IP_NO_CAPTURADA
