"""Pruebas de la composición de dependencias.

Cada componente se prueba en su módulo; acá se prueba que la composición le pase
lo que dice la configuración. Un parámetro omitido en `dependencies.py` no lo
detecta ninguna prueba del componente, que siempre lo construye completo.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from asn1crypto import x509 as asn1_x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from moto import mock_aws

from jurisdictions import get_profile
from pscnc.config import get_settings
from pscnc.crypto.ephemeral_ca import SubjectData
from pscnc.orchestrator import dependencies


def _limpiar_caches() -> None:
    get_settings.cache_clear()
    dependencies.build_signing_service.cache_clear()


@pytest.fixture()
def entorno_dev(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    ca_key: rsa.RSAPrivateKey,
    ca_certificate_der: bytes,
) -> Iterator[None]:
    """Configuración mínima con la que el servicio de firma arranca en `dev`."""
    clave = tmp_path / "ca.key.pem"
    clave.write_bytes(
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    certificado = tmp_path / "ca.der"
    certificado.write_bytes(ca_certificate_der)

    monkeypatch.delenv("AWS_PROFILE", raising=False)
    variables = {
        "PSCNC_ENVIRONMENT": "dev",
        "PSCNC_CRYPTO_BACKEND": "local",
        "PSCNC_LOCAL_CA_KEY_PATH": str(clave),
        "PSCNC_CA_CERT_PATH": str(certificado),
        "PSCNC_CRL_DISTRIBUTION_URL": "https://crl.pruebas.example/intermediate.crl",
        "PSCNC_TSA_URL": "https://tsa.pruebas.example",
        "PSCNC_TSA_PROVIDER_NAME": "TSA de pruebas",
        "PSCNC_SIGNED_BUCKET": "firmados-pruebas",
        "PSCNC_EVIDENCE_BUCKET": "evidencias-pruebas",
        "AWS_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
    }
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)

    _limpiar_caches()
    with mock_aws():
        yield
    _limpiar_caches()


def test_el_servicio_de_firma_de_dev_marca_el_certificado(entorno_dev: None) -> None:
    """Fuera de producción, todo artefacto va marcado: también por este camino.

    `build_signing_service` construía la autoridad sin pasarle el entorno, y el
    valor por defecto era `"prod"`: en dev emitía certificados con el sujeto de
    producción. Se lee la autoridad del servicio compuesto, no una construida en
    la prueba, porque lo que se fija es el cableado.
    """
    servicio = dependencies.build_signing_service()
    sujeto = SubjectData.for_jurisdiction(
        get_profile(get_settings().jurisdiction),
        given_name="María José",
        surname="Ruiz Díaz",
        national_id="4829153",
        transaction_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    )

    emitido = servicio._ca.issue(sujeto)
    unidad = asn1_x509.Certificate.load(emitido.certificate_der).subject.native[
        "organizational_unit_name"
    ]

    assert servicio._ca.environment == "dev"
    assert unidad.startswith("[NO VALIDO - ENTORNO DEV]")
