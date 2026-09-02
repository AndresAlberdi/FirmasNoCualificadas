"""Idempotencia de las escrituras del contrato público (ADR-0009).

Por qué es obligatoria y no una comodidad: una confirmación repetida —por un
reintento de red, por un tiempo de espera agotado del lado del tenant— debe
devolver **el acta original**. Dos actas para un mismo acto de firma son dos
piezas de evidencia divergentes sobre el mismo hecho, con sellos e instantes
distintos y ninguna forma de decidir cuál es la buena. Es material para impugnar
las dos.

Se ejercita a través de HTTP, que es donde la regla vive de verdad: el servicio
por sí solo no sabe nada de reintentos.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from conftest import KmsFiel
from pscnc.crypto.tenant_keys import TenantKeyRing
from pscnc.evidence.acta import ActaSealer
from pscnc.models.motivos import RejectionReason
from pscnc.orchestrator import app as modulo_app
from pscnc.orchestrator import rutas_v1
from pscnc.orchestrator.app import app
from pscnc.orchestrator.idempotencia import (
    IdempotencyControl,
    InMemoryIdempotencyStore,
    request_fingerprint,
)
from pscnc.orchestrator.security import (
    HEADER_CLIENT,
    HEADER_SIGNATURE,
    HEADER_TIMESTAMP,
    StaticSecretResolver,
    sign_request,
)
from pscnc.orchestrator.transacciones import (
    TransactionRepository,
    TransactionService,
)

SECRETO = b"secreto-de-pruebas"
TENANT = "segurolotengo"
CERRADO = datetime(2026, 9, 2, 14, 30, tzinfo=UTC)
HASH_DOC = "a" * 64

CUERPO_CREAR: dict[str, Any] = {
    "tenant_reference": "EXP-99887",
    "document": {
        "sha256": HASH_DOC,
        "version": 2,
        "code": "PROP-2026-000123",
        "closed_at": CERRADO.isoformat(),
    },
    "identity_decision": {
        "approved": True,
        "threshold_applied": 0.99,
        "score": 0.995,
        "score_scale": "0-100",
        "model_version": "rekognition-2026-07",
        "policy_version": "slt-identidad-v4",
        "provider_reference": "onb_72189312",
        "liveness_verified": True,
    },
}


def _cuerpo_confirmar() -> dict[str, Any]:
    return {
        "otp_proof": {
            "otp_reference": "otp_abc123",
            "channel": "WHATSAPP",
            "destination_masked": "+595 98* *** *56",
            "sent_at": CERRADO.isoformat(),
            "verified_at": (CERRADO + timedelta(seconds=40)).isoformat(),
        },
        "consent_statement": "Acepto firmar electrónicamente la propuesta y el FIPF.",
        "consent_statement_version": "p8-consentimiento-v3",
        "document_sha256": HASH_DOC,
    }


@pytest.fixture()
def entorno(monkeypatch: pytest.MonkeyPatch) -> TransactionService:
    """Cablea el servicio y el control de idempotencia con dobles."""
    kms = KmsFiel([f"alias/fnc/dev/{TENANT}/acta-seal/v1"])
    llavero = TenantKeyRing(TENANT, environment="dev", region="us-east-1", client=kms)
    servicio = TransactionService(
        repositorio=TransactionRepository(),
        sellador=ActaSealer(llavero),
        jurisdiccion_por_defecto="PY",
    )
    control = IdempotencyControl(InMemoryIdempotencyStore())

    import pscnc.orchestrator.dependencies as dependencias

    monkeypatch.setattr(dependencias, "build_transaction_service", lambda: servicio)
    monkeypatch.setattr(dependencias, "get_control_idempotencia", lambda: control)
    monkeypatch.setattr(
        modulo_app, "get_secret_resolver", lambda: StaticSecretResolver({TENANT: SECRETO})
    )
    monkeypatch.setattr(rutas_v1, "error_response", rutas_v1.error_response, raising=False)
    return servicio


@pytest.fixture()
def cliente() -> Any:
    with TestClient(app) as c:
        yield c


def _peticion(
    cliente: Any, metodo: str, ruta: str, cuerpo: dict[str, Any], clave: str | None
) -> Any:
    """Firma y envía una petición del contrato v1."""
    crudo = json.dumps(cuerpo).encode()
    instante = datetime.now(UTC).isoformat()
    cabeceras = {
        HEADER_CLIENT: TENANT,
        HEADER_TIMESTAMP: instante,
        HEADER_SIGNATURE: sign_request(SECRETO, metodo, ruta, instante, crudo),
        "content-type": "application/json",
    }
    if clave:
        cabeceras["Idempotency-Key"] = clave
    return cliente.request(metodo, ruta, content=crudo, headers=cabeceras)


class TestClaveObligatoria:
    def test_sin_clave_no_se_crea_una_transaccion(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        respuesta = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, None)

        assert respuesta.status_code == 400
        assert respuesta.json()["motivo"] == RejectionReason.IDEMPOTENCY_KEY_REQUIRED.value

    def test_el_mensaje_explica_la_consecuencia(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        """Un rechazo que no explica el porqué se resuelve quitando el control."""
        respuesta = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, None)

        assert "acta nueva" in respuesta.json()["mensaje"]


class TestRepeticion:
    def test_crear_dos_veces_con_la_misma_clave_devuelve_la_misma_transaccion(
        self, cliente, entorno
    ) -> None:  # type: ignore[no-untyped-def]
        primera = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-1")
        segunda = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-1")

        assert primera.status_code == 201
        assert segunda.status_code == 201
        assert primera.json()["transaction_id"] == segunda.json()["transaction_id"]

    def test_la_repeticion_se_declara_en_una_cabecera(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        """Sin esta señal, un reintento parece un segundo acto."""
        _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-2")
        segunda = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-2")

        assert segunda.headers.get("Idempotency-Replayed") == "true"

    def test_confirmar_dos_veces_devuelve_el_acta_original(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        """El caso que da sentido a toda la regla."""
        creada = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-3").json()
        ruta = f"/v1/transactions/{creada['transaction_id']}/confirm"

        primera = _peticion(cliente, "POST", ruta, _cuerpo_confirmar(), "c-3")
        segunda = _peticion(cliente, "POST", ruta, _cuerpo_confirmar(), "c-3")

        assert primera.status_code == 200
        assert segunda.status_code == 200
        # El acta es idéntica: mismo sello, mismo instante, mismo código.
        assert primera.json()["acta"]["jws"] == segunda.json()["acta"]["jws"]
        assert primera.json()["confirmed_at"] == segunda.json()["confirmed_at"]
        assert primera.json()["verification_code"] == segunda.json()["verification_code"]

    def test_sin_clave_repetida_la_segunda_confirmacion_se_rechaza(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        """Distinto de la repetición: acá el tenant pidió un acto nuevo."""
        creada = _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-4").json()
        ruta = f"/v1/transactions/{creada['transaction_id']}/confirm"

        _peticion(cliente, "POST", ruta, _cuerpo_confirmar(), "c-4a")
        segunda = _peticion(cliente, "POST", ruta, _cuerpo_confirmar(), "c-4b")

        assert segunda.status_code == 409
        assert segunda.json()["motivo"] == RejectionReason.TRANSACTION_ALREADY_CONFIRMED.value


class TestConflicto:
    def test_la_misma_clave_con_otro_cuerpo_se_rechaza(self, cliente, entorno) -> None:  # type: ignore[no-untyped-def]
        """Devolver la primera respuesta sería peor que fallar.

        El tenant creería que su segunda petición —con otro documento— se aplicó.
        """
        _peticion(cliente, "POST", "/v1/transactions", CUERPO_CREAR, "k-5")

        distinto = json.loads(json.dumps(CUERPO_CREAR))
        distinto["document"]["sha256"] = "f" * 64
        segunda = _peticion(cliente, "POST", "/v1/transactions", distinto, "k-5")

        assert segunda.status_code == 409
        assert segunda.json()["motivo"] == RejectionReason.IDEMPOTENCY_CONFLICT.value


class TestAislamientoDeClaves:
    def test_la_huella_incluye_al_inquilino(self) -> None:
        """Dos tenants pueden elegir la misma clave sin saberlo."""
        de_a = request_fingerprint("tenant-a", "/v1/transactions", b"{}")
        de_b = request_fingerprint("tenant-b", "/v1/transactions", b"{}")

        assert de_a != de_b

    def test_la_huella_incluye_la_ruta(self) -> None:
        """La misma clave en dos endpoints distintos son dos operaciones."""
        crear = request_fingerprint("t", "/v1/transactions", b"{}")
        confirmar = request_fingerprint("t", "/v1/transactions/x/confirm", b"{}")

        assert crear != confirmar

    def test_la_clave_lleva_espacio_de_nombres_por_inquilino(self) -> None:
        """Sin esto, una colisión de nombres sería una fuga entre clientes."""
        a = IdempotencyControl.clave_completa("tenant-a", "k")
        b = IdempotencyControl.clave_completa("tenant-b", "k")

        assert a != b

    def test_fuera_de_ventana_la_clave_queda_libre(self) -> None:
        """Retener respuestas para siempre haría del almacén un registro paralelo."""
        control = IdempotencyControl(InMemoryIdempotencyStore(), ventana=timedelta(seconds=0))
        control.registrar(
            tenant_id=TENANT,
            clave="k",
            ruta="/v1/transactions",
            cuerpo=b"{}",
            status_code=201,
            body={"transaction_id": "x"},
        )

        assert (
            control.recuperar(tenant_id=TENANT, clave="k", ruta="/v1/transactions", cuerpo=b"{}")
            is None
        )
