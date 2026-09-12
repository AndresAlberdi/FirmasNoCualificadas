"""La condición de cualificado del sello de tiempo se declara, no se presume.

Fuera de producción el sello viene de una autoridad de pruebas: acredita que el
sistema funciona, no la fecha cierta del acto, y el acta tiene que decirlo con
`timestamp.qualified: false`. Mientras el parámetro valió `True` por defecto,
cualquier llamador que lo omitiera producía en dev o staging un sello declarado
cualificado, y el acta lo publicaba como tal.

Estas pruebas fijan que en ningún punto del recorrido del sello —de la fábrica de
selladores al acta— haya un valor por defecto que decida por el llamador. Si
alguien vuelve a ponerle uno, fallan.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from pscnc.crypto.pades import build_timestamper_factory
from pscnc.crypto.tsa import RecordingTimeStamper, TimestampResult, parse_timestamp_token
from pscnc.evidence.acta import ActaPayload, DocumentReference

PUNTOS_DEL_RECORRIDO: list[tuple[Callable[..., object], str]] = [
    (build_timestamper_factory, "qualified"),
    (RecordingTimeStamper, "qualified"),
    (parse_timestamp_token, "qualified"),
    (TimestampResult, "qualified"),
    (ActaPayload, "timestamp_qualified"),
]


@pytest.mark.parametrize(
    ("invocable", "parametro"),
    PUNTOS_DEL_RECORRIDO,
    ids=[invocable.__name__ for invocable, _ in PUNTOS_DEL_RECORRIDO],
)
def test_la_condicion_de_cualificado_es_obligatoria_y_por_nombre(
    invocable: Callable[..., object], parametro: str
) -> None:
    """Sin valor por defecto, y solo por nombre para que no se confunda de posición."""
    declarado = inspect.signature(invocable).parameters[parametro]

    assert declarado.default is inspect.Parameter.empty, (
        f"`{parametro}` de {invocable.__name__} tiene un valor por defecto: "
        "omitirlo decidiría por el llamador si el sello es cualificado"
    )
    assert declarado.kind is inspect.Parameter.KEYWORD_ONLY


# Las llamadas de abajo omiten el argumento a propósito: es lo que se prueba.
# El verificador de tipos las rechazaría, que es justamente la otra mitad de la
# protección; acá se comprueba la que queda en tiempo de ejecución.


def test_la_fabrica_de_selladores_no_se_construye_sin_declararla() -> None:
    with pytest.raises(TypeError, match="qualified"):
        build_timestamper_factory(  # type: ignore[call-arg]  # omisión deliberada
            url="https://tsa.pruebas.example", provider_name="TSA de Pruebas"
        )


def test_el_sellador_no_se_construye_sin_declararla(tsa_material: tuple[object, object]) -> None:
    from pyhanko.sign.timestamps import DummyTimeStamper

    tsa_cert, tsa_key = tsa_material
    with pytest.raises(TypeError, match="qualified"):
        RecordingTimeStamper(  # type: ignore[call-arg]  # omisión deliberada
            "",
            provider_name="TSA de Pruebas",
            delegate=DummyTimeStamper(tsa_cert=tsa_cert, tsa_key=tsa_key),
        )


def test_el_resultado_del_sellado_no_se_construye_sin_declararla() -> None:
    with pytest.raises(TypeError, match="qualified"):
        TimestampResult(  # type: ignore[call-arg]  # omisión deliberada
            provider_name="TSA de Pruebas",
            token_base64="AAAA",
            gen_time=datetime.now(UTC),
            serial_number="1",
            certificate_chain_pem=["-----BEGIN CERTIFICATE-----"],
        )


def test_el_acta_no_se_construye_sin_declararla() -> None:
    with pytest.raises(TypeError, match="timestamp_qualified"):
        ActaPayload(  # type: ignore[call-arg]  # omisión deliberada
            tenant_id="tenant-a",
            transaction_id="tx-1",
            jurisdiction="PY",
            service_level=2,
            environment="dev",
            document=DocumentReference(
                sha256="a" * 64, version=1, code="DOC-1", closed_at=datetime.now(UTC)
            ),
            evidence_sha256="b" * 64,
            timestamp_token_sha256="c" * 64,
            timestamp_authority="TSA de Pruebas",
        )


@pytest.mark.parametrize("cualificado", [True, False])
def test_el_acta_publica_lo_que_se_declaro(cualificado: bool) -> None:
    """Lo declarado llega tal cual al payload que se sella."""
    acta = ActaPayload(
        tenant_id="tenant-a",
        transaction_id="tx-1",
        jurisdiction="PY",
        service_level=2,
        environment="dev",
        document=DocumentReference(
            sha256="a" * 64, version=1, code="DOC-1", closed_at=datetime.now(UTC)
        ),
        evidence_sha256="b" * 64,
        timestamp_token_sha256="c" * 64,
        timestamp_authority="TSA de Pruebas",
        timestamp_qualified=cualificado,
    )

    assert acta.to_payload(sealed_at=datetime.now(UTC))["timestamp"]["qualified"] is cualificado
