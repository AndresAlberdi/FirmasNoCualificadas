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

from jurisdictions import get_profile
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData

CRL_URL = "https://crl.pruebas.example.py/pscnc/intermediate.crl"
POLICY_OID = "1.3.6.1.4.1.99999.1.1.1"
CPS_URL = "https://pruebas.example.py/dpc"
AVISO = "Sujeto a las condiciones de uso expuestas en la Declaración de Prácticas."


@pytest.fixture()
def autoridad(ca_certificate_der, ca_signer):  # type: ignore[no-untyped-def]
    return EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url=CRL_URL,
        policy_oid=POLICY_OID,
        cps_url=CPS_URL,
        user_notice=AVISO,
        backdate_minutes=5,
        validity_minutes=15,
    )


@pytest.fixture()
def sujeto() -> SubjectData:
    return SubjectData.for_jurisdiction(
        get_profile("PY"),
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
    # Sigla del documento y no código de país: es lo que exige el perfil nacional.
    assert nombre["serial_number"] == "CI4829153"
    assert nombre["country_name"] == "PY"
    # El `O` declara qué clase de certificado es, con el literal que fija el perfil.
    assert nombre["organization_name"] == "CERTIFICADO NO CUALIFICADO DE FIRMA ELECTRÓNICA"
    # En producción la unidad organizativa vale exactamente lo que fija el perfil:
    # el campo no admite agregados, ni siquiera el identificador de transacción.
    assert nombre["organizational_unit_name"] == "FIRMA ELECTRÓNICA"


def test_en_produccion_la_unidad_organizativa_no_lleva_nada_mas(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    """El vínculo con la transacción no se pierde: vive en el número de serie.

    El acta sellada registra el serial del certificado, así que el certificado y la
    transacción siguen ligados sin necesidad de escribir el identificador en un
    campo cuyo valor fija la norma.
    """
    emitido = autoridad.issue(sujeto)
    nombre = asn1_x509.Certificate.load(emitido.certificate_der).subject.native

    assert sujeto.transaction_id not in nombre["organizational_unit_name"]
    assert emitido.serial_number


def test_fuera_de_produccion_el_certificado_se_rotula_como_invalido(  # type: ignore[no-untyped-def]
    ca_certificate_der, ca_signer, sujeto
) -> None:
    """La marca vive en un campo que cualquier visor muestra sin desplegar extensiones.

    Apartarse del perfil acá no es un incumplimiento: en `dev` no somos un prestador
    comunicado y el certificado no pretende ser oponible. La desviación **es** la
    señal de que el artefacto no sirve como prueba.
    """
    autoridad_dev = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url=CRL_URL,
        policy_oid=POLICY_OID,
        environment="dev",
    )

    emitido = autoridad_dev.issue(sujeto)
    unidad = asn1_x509.Certificate.load(emitido.certificate_der).subject.native[
        "organizational_unit_name"
    ]

    assert unidad.startswith("[NO VALIDO - ENTORNO DEV]")
    assert "FIRMA ELECTRÓNICA" in unidad


def test_los_dos_entornos_no_emiten_el_mismo_sujeto(  # type: ignore[no-untyped-def]
    autoridad, ca_certificate_der, ca_signer, sujeto
) -> None:
    """Es la propiedad que sostiene la marca: si coincidieran, no distinguiría nada."""
    autoridad_dev = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url=CRL_URL,
        environment="dev",
    )

    en_prod = asn1_x509.Certificate.load(autoridad.issue(sujeto).certificate_der).subject.native
    en_dev = asn1_x509.Certificate.load(autoridad_dev.issue(sujeto).certificate_der).subject.native

    assert en_prod["organizational_unit_name"] != en_dev["organizational_unit_name"]


def test_el_pasaporte_produce_una_sigla_distinta(autoridad) -> None:  # type: ignore[no-untyped-def]
    """Un certificado que dijera «CI» sobre un pasaporte afirmaría un documento falso."""
    con_pasaporte = SubjectData.for_jurisdiction(
        get_profile("PY"),
        common_name="Firmante De Prueba",
        national_id="AB123456",
        document_type="PASAPORTE",
    )

    emitido = autoridad.issue(con_pasaporte)
    nombre = asn1_x509.Certificate.load(emitido.certificate_der).subject.native

    assert nombre["serial_number"] == "PASAB123456"


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
    # Los tres bits que el perfil marca en 1, y los que marca en 0.
    assert uso.value.digital_signature is True
    assert uso.value.content_commitment is True  # non_repudiation
    assert uso.value.key_encipherment is True
    assert uso.value.data_encipherment is False
    assert uso.value.key_agreement is False
    assert uso.value.key_cert_sign is False
    assert uso.value.crl_sign is False

    puntos = extensiones.get_extension_for_class(cx509.CRLDistributionPoints)
    assert CRL_URL in str(puntos.value[0].full_name[0].value)

    politicas = extensiones.get_extension_for_class(cx509.CertificatePolicies)
    assert politicas.value[0].policy_identifier.dotted_string == POLICY_OID

    assert extensiones.get_extension_for_class(cx509.AuthorityKeyIdentifier) is not None


def test_el_uso_extendido_incluye_el_de_autenticacion_de_cliente(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    """El perfil enumera dos OID: protección de correo y autenticación de cliente."""
    emitido = autoridad.issue(sujeto)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)
    usos = {
        oid.dotted_string
        for oid in certificado.extensions.get_extension_for_class(cx509.ExtendedKeyUsage).value
    }

    assert "1.3.6.1.5.5.7.3.4" in usos  # emailProtection
    assert "1.3.6.1.5.5.7.3.2" in usos  # clientAuth


def test_la_politica_lleva_sus_dos_calificadores(autoridad, sujeto) -> None:  # type: ignore[no-untyped-def]
    """Un identificador suelto no dice dónde leer las condiciones de emisión.

    Es para lo que sirve la extensión, y el perfil exige los dos calificadores
    además del identificador.
    """
    emitido = autoridad.issue(sujeto)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)
    politica = certificado.extensions.get_extension_for_class(cx509.CertificatePolicies).value[0]

    calificadores = politica.policy_qualifiers
    assert CPS_URL in calificadores
    avisos = [c for c in calificadores if isinstance(c, cx509.UserNotice)]
    assert avisos and avisos[0].explicit_text == AVISO


def test_sin_calificadores_configurados_no_se_inventan(  # type: ignore[no-untyped-def]
    ca_certificate_der, ca_signer, sujeto
) -> None:
    """Una URL que no sirve la declaración de prácticas es peor que ninguna."""
    autoridad_minima = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url=CRL_URL,
        policy_oid=POLICY_OID,
    )

    emitido = autoridad_minima.issue(sujeto)
    certificado = cx509.load_der_x509_certificate(emitido.certificate_der)
    politica = certificado.extensions.get_extension_for_class(cx509.CertificatePolicies).value[0]

    assert politica.policy_identifier.dotted_string == POLICY_OID
    assert politica.policy_qualifiers is None


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
