"""Composición de dependencias: lo que el entorno decide sobre los artefactos.

`dependencies.py` es el único lugar donde se elige la implementación según el
entorno, y por eso también el único donde puede olvidarse una marca de entorno.
Estas pruebas construyen el servicio con la configuración real y miran lo que
sale de él, en vez de repetir los argumentos con que se lo armó.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from moto import mock_aws

from pscnc.config import get_settings
from pscnc.crypto.tsa import RecordingTimeStamper
from pscnc.orchestrator import dependencies
from pscnc.orchestrator.state_machine import SigningService


@pytest.fixture()
def configuracion(monkeypatch, tmp_path, ca_certificate_der, ca_signer) -> Iterator[None]:  # type: ignore[no-untyped-def]
    """Configuración completa del flujo heredado; el entorno lo fija cada prueba."""
    ruta_ca = tmp_path / "ca.der"
    ruta_ca.write_bytes(ca_certificate_der)
    variables = {
        # `kms` porque es el único backend admitido en staging y prod.
        "PSCNC_CRYPTO_BACKEND": "kms",
        "PSCNC_KMS_CA_KEY_ID": "alias/pruebas",
        "PSCNC_CA_CERT_PATH": str(ruta_ca),
        "PSCNC_TSA_URL": "https://tsa.pruebas.example",
        "PSCNC_TSA_PROVIDER_NAME": "TSA de Pruebas",
        "PSCNC_CRL_DISTRIBUTION_URL": "https://crl.pruebas.example/ca.crl",
        "PSCNC_SIGNED_BUCKET": "firmados",
        "PSCNC_EVIDENCE_BUCKET": "evidencias",
        "AWS_REGION": "us-east-1",
        # Los repositorios crean su cliente al construirse: con credenciales
        # ficticias no leen el perfil de quien corre la prueba.
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
    }
    for nombre, valor in variables.items():
        monkeypatch.setenv(nombre, valor)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    # La CA la firma un doble: lo que se prueba es la composición, no KMS.
    monkeypatch.setattr(dependencies, "build_ca_signer", lambda _settings: ca_signer)
    get_settings.cache_clear()
    dependencies.build_signing_service.cache_clear()
    with mock_aws():
        yield
    get_settings.cache_clear()
    dependencies.build_signing_service.cache_clear()


def _servicio(monkeypatch: pytest.MonkeyPatch, entorno: str) -> SigningService:
    monkeypatch.setenv("PSCNC_ENVIRONMENT", entorno)
    return dependencies.build_signing_service()


def _sellador(servicio: SigningService) -> RecordingTimeStamper:
    # Se invoca la fábrica igual que la invoca el firmante en cada transacción.
    sellador: RecordingTimeStamper = servicio._signer._timestamper_factory()
    return sellador


class TestFlujoHeredado:
    """`build_signing_service`, que arma el flujo de `/v1/signing-sessions`."""

    @pytest.mark.parametrize("entorno", ["dev", "staging"])
    def test_fuera_de_prod_el_sello_no_se_declara_cualificado(  # type: ignore[no-untyped-def]
        self, configuracion, monkeypatch, entorno
    ) -> None:
        """Un sello de prueba acredita que el sistema funciona, no la fecha cierta.

        Declararlo cualificado haría que la evidencia afirmara una fecha cierta
        que ningún prestador cualificado otorgó.
        """
        assert _sellador(_servicio(monkeypatch, entorno)).qualified is False

    def test_en_prod_el_sello_se_declara_cualificado(  # type: ignore[no-untyped-def]
        self, configuracion, monkeypatch
    ) -> None:
        """Contraprueba: sin ella, la anterior pasaría con un sellador que nunca lo es."""
        assert _sellador(_servicio(monkeypatch, "prod")).qualified is True
