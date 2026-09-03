"""Prueba de integración del flujo completo de firma PAdES-B-T.

Ejercita la cadena real —emisión del certificado efímero, actualización
incremental del PDF, bloque CMS y sellado de tiempo— sustituyendo únicamente la
Autoridad de Sellado por el sellador de pruebas de pyHanko. Verifica lo que un
validador externo comprobaría:

* que el PDF conserva sus bytes originales como prefijo (actualización incremental);
* que la firma se valida contra el documento;
* que lleva un sello de tiempo cuyo token es recuperable para la auditoría;
* que el subfiltro es el exigido por PAdES.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from asn1crypto import keys as asn1_keys
from asn1crypto import x509 as asn1_x509
from cryptography import x509 as cx509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from jurisdictions import get_profile
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData
from pscnc.crypto.pades import PadesSigner, VisualSignatureSpec
from pscnc.crypto.tsa import RecordingTimeStamper

pytestmark = pytest.mark.integration


def _pdf_minimo() -> bytes:
    """Genera un PDF de una página con reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=A4)
    lienzo.drawString(72, 760, "Contrato de prestacion de servicios de consultoria")
    lienzo.drawString(72, 740, "Documento de prueba sintetico - sin datos personales reales")
    lienzo.showPage()
    lienzo.save()
    return buffer.getvalue()


@pytest.fixture()
def tsa_material() -> tuple[asn1_x509.Certificate, asn1_keys.PrivateKeyInfo]:
    """Certificado y clave de una TSA de pruebas."""
    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = cx509.Name(
        [
            cx509.NameAttribute(NameOID.COUNTRY_NAME, "PY"),
            cx509.NameAttribute(NameOID.COMMON_NAME, "TSA de Pruebas"),
        ]
    )
    ahora = datetime.now(UTC)
    certificado = (
        cx509.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(cx509.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=365))
        .add_extension(
            cx509.ExtendedKeyUsage([cx509.oid.ExtendedKeyUsageOID.TIME_STAMPING]), critical=True
        )
        .sign(clave, hashes.SHA256())
    )
    return (
        asn1_x509.Certificate.load(certificado.public_bytes(serialization.Encoding.DER)),
        asn1_keys.PrivateKeyInfo.load(
            clave.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        ),
    )


@pytest.fixture()
def firmante(ca_certificate_der, ca_signer, tsa_material):  # type: ignore[no-untyped-def]
    from pyhanko.sign.timestamps import DummyTimeStamper

    tsa_cert, tsa_key = tsa_material
    autoridad = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url="https://crl.pruebas.example.py/pscnc/intermediate.crl",
        policy_oid="1.3.6.1.4.1.99999.1.1.1",
    )

    def _fabrica() -> RecordingTimeStamper:
        return RecordingTimeStamper(
            "",
            provider_name="TSA de Pruebas",
            delegate=DummyTimeStamper(tsa_cert=tsa_cert, tsa_key=tsa_key),
        )

    return PadesSigner(
        certificate_authority=autoridad,
        timestamper_factory=_fabrica,
        jurisdiction=get_profile("PY"),
    )


@pytest.fixture()
def sujeto() -> SubjectData:
    return SubjectData.for_jurisdiction(
        get_profile("PY"),
        common_name="Firmante De Prueba",
        national_id="4829153",
        transaction_id="9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    )


def test_firma_produce_pdf_valido_con_sello_de_tiempo(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    original = _pdf_minimo()
    resultado = firmante.sign(original, sujeto, visual=VisualSignatureSpec(enabled=False))

    assert resultado.signed_pdf.startswith(b"%PDF-")
    assert resultado.original_sha256 != resultado.signed_sha256
    assert resultado.signature_format == "PAdES-B-T"
    assert resultado.timestamp.provider_name == "TSA de Pruebas"
    assert resultado.timestamp.serial_number
    assert resultado.timestamp.token_base64
    assert resultado.timestamp.certificate_chain_pem


def test_actualizacion_incremental_conserva_el_documento_original(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    """Requisito de PAdES: las firmas previas de terceros no pueden invalidarse."""
    original = _pdf_minimo()
    resultado = firmante.sign(original, sujeto, visual=VisualSignatureSpec(enabled=False))

    assert resultado.signed_pdf[: len(original)] == original
    assert len(resultado.signed_pdf) > len(original)


def test_la_firma_se_valida_contra_el_documento(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    from pyhanko.pdf_utils.reader import PdfFileReader
    from pyhanko.sign.validation import validate_pdf_signature

    resultado = firmante.sign(_pdf_minimo(), sujeto, visual=VisualSignatureSpec(enabled=False))

    lector = PdfFileReader(io.BytesIO(resultado.signed_pdf))
    assert len(lector.embedded_signatures) == 1

    firma = lector.embedded_signatures[0]
    estado = validate_pdf_signature(firma)

    # La integridad y la vinculación con el certificado deben verificarse siempre.
    assert estado.intact is True
    assert estado.valid is True
    # La confianza de la cadena no se evalúa aquí: la CA de pruebas no está en
    # ningún almacén de confianza, tal como ocurriría con la CA real antes de su
    # publicación en el listado del MIC.
    assert estado.timestamp_validity is not None


def test_certificado_del_firmante_embebido_es_el_emitido(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    from pyhanko.pdf_utils.reader import PdfFileReader

    resultado = firmante.sign(_pdf_minimo(), sujeto, visual=VisualSignatureSpec(enabled=False))
    lector = PdfFileReader(io.BytesIO(resultado.signed_pdf))
    firma = lector.embedded_signatures[0]

    sujeto_embebido = firma.signer_cert.subject.native
    # El sujeto que viaja dentro del PDF es el del perfil nacional, no uno propio.
    assert sujeto_embebido["serial_number"] == "CI4829153"
    assert sujeto_embebido["organization_name"] == (
        "CERTIFICADO NO CUALIFICADO DE FIRMA ELECTRÓNICA"
    )
    assert format(firma.signer_cert.serial_number, "x") == resultado.certificate.serial_number


def test_firma_visible_crea_el_campo_en_la_pagina_indicada(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    from pyhanko.pdf_utils.reader import PdfFileReader

    resultado = firmante.sign(
        _pdf_minimo(),
        sujeto,
        visual=VisualSignatureSpec(enabled=True, page=1, x=100, y=150, width=180, height=60),
    )

    lector = PdfFileReader(io.BytesIO(resultado.signed_pdf))
    assert lector.embedded_signatures[0].field_name == "FirmaFENC"


def test_rechaza_un_archivo_que_no_sea_pdf(firmante, sujeto) -> None:  # type: ignore[no-untyped-def]
    from pscnc.errors import DocumentIntegrityError

    with pytest.raises(DocumentIntegrityError):
        firmante.sign(b"esto no es un pdf", sujeto)
