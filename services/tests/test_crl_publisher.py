"""Pruebas de la generación de la Lista de Revocación de Certificados.

Una CRL malformada o vencida hace que los validadores rechacen firmas válidas,
por lo que se verifica el artefacto con una librería independiente de la que lo
construye.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from cryptography import x509 as cx509

from pscnc.jobs.crl_publisher import build_crl


def test_crl_valida_y_firmada_por_la_ca(ca_certificate_der, ca_signer, ca_key) -> None:  # type: ignore[no-untyped-def]
    contenido = build_crl(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_number=7,
        validity_hours=72,
    )
    lista = cx509.load_der_x509_crl(contenido)

    assert lista.is_signature_valid(ca_key.public_key()) is True
    assert len(list(lista)) == 0
    assert lista.extensions.get_extension_for_class(cx509.CRLNumber).value.crl_number == 7
    assert lista.extensions.get_extension_for_class(cx509.AuthorityKeyIdentifier) is not None


def test_next_update_refleja_la_vigencia_declarada(ca_certificate_der, ca_signer) -> None:  # type: ignore[no-untyped-def]
    """El campo nextUpdate vencido hace que Adobe rechace la firma: debe ser correcto."""
    instante = datetime.now(UTC)
    contenido = build_crl(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_number=1,
        validity_hours=48,
        now=instante,
    )
    lista = cx509.load_der_x509_crl(contenido)

    diferencia = lista.next_update_utc - lista.last_update_utc
    assert diferencia == timedelta(hours=48)
    assert lista.next_update_utc > instante


def test_revocacion_de_emergencia_incluye_la_razon(ca_certificate_der, ca_signer) -> None:  # type: ignore[no-untyped-def]
    """Escenario del runbook: compromiso de la clave de la CA intermedia."""
    ca = cx509.load_der_x509_certificate(ca_certificate_der)
    instante = datetime.now(UTC)

    contenido = build_crl(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_number=99,
        revoked=[{"serial": ca.serial_number, "date": instante, "reason": "key-compromise"}],
    )
    lista = cx509.load_der_x509_crl(contenido)
    entradas = list(lista)

    assert len(entradas) == 1
    assert entradas[0].serial_number == ca.serial_number
    razon = entradas[0].extensions.get_extension_for_class(cx509.CRLReason).value.reason
    assert razon == cx509.ReasonFlags.key_compromise
