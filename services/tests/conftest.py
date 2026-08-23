"""Utilidades comunes de las pruebas.

Todos los datos son sintéticos. Está prohibido incorporar cédulas, nombres,
documentos o imágenes de personas reales a los fixtures (ver CONTRIBUTING.md).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric import utils as asym_utils
from cryptography.x509.oid import NameOID

from pscnc.models.audit_trail import (
    ConsentEvidence,
    IdentityEvidence,
    NetworkEvidence,
    OtpLog,
)

CEDULA_SINTETICA = "4829153"


class FakeCaSigner:
    """Firmante de CA en memoria para pruebas: misma interfaz que ``KmsCaSigner``."""

    def __init__(self, private_key: rsa.RSAPrivateKey) -> None:
        self._private_key = private_key

    @property
    def signing_algorithm(self) -> str:
        return "RSASSA_PKCS1_V1_5_SHA_256"

    def sign_digest(self, digest: bytes) -> bytes:
        assert len(digest) == 32
        return self._private_key.sign(
            digest, padding.PKCS1v15(), asym_utils.Prehashed(hashes.SHA256())
        )

    def public_key_der(self) -> bytes:
        return self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )


@pytest.fixture(scope="session")
def ca_key() -> rsa.RSAPrivateKey:
    # 2048 bits en pruebas: la generación de 4096 encarece la batería sin aportar cobertura.
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="session")
def ca_certificate_der(ca_key: rsa.RSAPrivateKey) -> bytes:
    """Certificado autofirmado que simula la CA intermedia del PSCNC."""
    sujeto = cx509.Name(
        [
            cx509.NameAttribute(NameOID.COUNTRY_NAME, "PY"),
            cx509.NameAttribute(NameOID.ORGANIZATION_NAME, "PSCNC Pruebas S.A."),
            cx509.NameAttribute(NameOID.COMMON_NAME, "CA Intermedia FENC - Pruebas"),
        ]
    )
    ahora = datetime.now(UTC)
    certificado = (
        cx509.CertificateBuilder()
        .subject_name(sujeto)
        .issuer_name(sujeto)
        .public_key(ca_key.public_key())
        .serial_number(cx509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=3650))
        .add_extension(cx509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            cx509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            cx509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False
        )
        .sign(ca_key, hashes.SHA256())
    )
    return certificado.public_bytes(serialization.Encoding.DER)


@pytest.fixture()
def ca_signer(ca_key: rsa.RSAPrivateKey) -> FakeCaSigner:
    return FakeCaSigner(ca_key)


@pytest.fixture()
def identidad() -> IdentityEvidence:
    return IdentityEvidence(
        document_type="CI_PY",
        national_id=CEDULA_SINTETICA,
        first_name="Firmante",
        last_name="De Prueba",
        birth_date=date(1985, 3, 14),
        ocr_mrz_raw="IDPRY4829153<<<<<<<<<<<<<<<<8503140M3001019PRY<<<<<<<<<<<8",
        ocr_confidence=0.99,
        facial_match_score=0.985,
        liveness_detected=True,
        verification_partner_id="proveedor-pruebas",
        aml_pep_checked=True,
        aml_pep_result="SIN COINCIDENCIAS",
    )


@pytest.fixture()
def red() -> NetworkEvidence:
    return NetworkEvidence(
        client_ip="190.104.128.5",
        source_port=51234,
        user_agent="Mozilla/5.0 (pruebas)",
        tls_version="TLSv1.3",
        tls_cipher="TLS_AES_256_GCM_SHA384",
    )


@pytest.fixture()
def consentimiento() -> ConsentEvidence:
    ahora = datetime.now(UTC)
    return ConsentEvidence(
        explicit_consent_checked=True,
        consent_statement="Acepto firmar electronicamente el documento identificado.",
        otp_channels=[
            OtpLog(
                channel_type="WHATSAPP",
                destination="+595981000000",
                otp_sent_timestamp=ahora - timedelta(seconds=30),
                otp_verified_timestamp=ahora,
                provider_message_id="msg-pruebas-1",
                otp_code_hash="a" * 64,
            )
        ],
    )
