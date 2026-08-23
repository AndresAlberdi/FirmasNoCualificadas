"""Pruebas de la emisión de certificados efímeros del firmante.

Se verifica lo que un perito comprobaría: que el certificado está firmado por la
CA declarada, que su sujeto identifica a la persona con el formato del perfil
nacional y que su vigencia es la ventana corta que sostiene el modelo (ADR-0004).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from asn1crypto import x509 as asn1_x509
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData

CRL_URL = "https://crl.pruebas.example.py/pscnc/intermediate.crl"
POLICY_OID = "1.3.6.1.4.1.99999.1.1.1"


@pytest.fixture()
def autoridad(ca_certificate_der, ca_signer):  # type: ignore[no-untyped-def]
    return EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url=CRL_URL,
        policy_oid=POLICY_OID,
        backdate_minutes=5,
        validity_minutes=15,
    )


@pytest.fixture()
def sujeto() -> SubjectData:
    return SubjectData(
        common_name="Firmante De Prueba",
        national_id="4829153",
        transaction_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    )


def test_certificado_firmado_por_la_ca(autoridad, sujeto, ca_key) -> None:  # type: ignore[no-untyped-def]
    """La firma del certificado debe validar contra la clave pública de la CA."""
    emitido = autoridad.issue(sujeto)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)

    ca_key.public_key().verify(
        certificado.signature,
        certificado.tbs_certificate_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


def test_sujeto_conforme_al_perfil_nacional(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    emitido = autoridad.issue(sujeto)
    nombre = asn1_x509.Certificate.load(emitido.certificate_der).subject.native

    assert nombre["common_name"] == "Firmante De Prueba"
    assert nombre["serial_number"] == "PY-4829153"
    assert nombre["country_name"] == "PY"
    assert sujeto.transaction_id in nombre["organizational_unit_name"]


def test_ventana_de_vigencia_corta(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    """15 minutos de vigencia con 5 de retroceso: no debe ser reutilizable."""
    ahora = datetime.now(UTC)
    emitido = autoridad.issue(sujeto, now=ahora)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)

    duracion = certificado.not_valid_after_utc - certificado.not_valid_before_utc
    assert duracion.total_seconds() == pytest.approx(20 * 60, abs=2)
    assert certificado.not_valid_before_utc <= ahora <= certificado.not_valid_after_utc


def test_extensiones_obligatorias(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    emitido = autoridad.issue(sujeto)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)
    extensiones = certificado.extensions

    restricciones = extensiones.get_extension_for_class(cx509.BasicConstraints)
    assert restricciones.value.ca is False
    assert restricciones.critical is True

    uso = extensiones.get_extension_for_class(cx509.KeyUsage)
    assert uso.critical is True
    assert uso.value.digital_signature is True
    assert uso.value.content_commitment is True  # non_repudiation
    assert uso.value.key_cert_sign is False

    puntos = extensiones.get_extension_for_class(cx509.CRLDistributionPoints)
    assert CRL_URL in str(puntos.value[0].full_name[0].value)

    politicas = extensiones.get_extension_for_class(cx509.CertificatePolicies)
    assert politicas.value[0].policy_identifier.dotted_string == POLICY_OID

    assert extensiones.get_extension_for_class(cx509.AuthorityKeyIdentifier) is not None


def test_cada_emision_usa_una_clave_y_serie_distintas(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    """Los certificados son de un solo uso: nada puede reutilizarse entre firmas."""
    primero = autoridad.issue(sujeto)
    segundo = autoridad.issue(sujeto)

    assert primero.serial_number != segundo.serial_number
    assert primero.private_key_pem != segundo.private_key_pem
    assert primero.certificate_der != segundo.certificate_der


def test_rechaza_un_certificado_que_no_sea_de_ca(ca_signer) -> None:  # type: ignore[no-untyped-def]
    """Configurar una hoja como CA intermedia debe fallar al arrancar, no al firmar."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = cx509.Name([cx509.NameAttribute(NameOID.COMMON_NAME, "hoja")])
    ahora = datetime.now(UTC)
    hoja = (
        cx509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(cx509.random_serial_number())
        .not_valid_before(ahora)
        .not_valid_after(ahora.replace(year=ahora.year + 1))
        .add_extension(cx509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(clave, hashes.SHA256())
    )

    with pytest.raises(Exception, match="CA:TRUE"):
        EphemeralCertificateAuthority(
            ca_certificate_der=hoja.public_bytes(serialization.Encoding.DER),
            ca_signer=ca_signer,
            crl_url=CRL_URL,
        )
