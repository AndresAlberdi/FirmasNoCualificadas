"""Pruebas del modelo de la pista de auditoría.

El objetivo no es validar Pydantic sino verificar las invariantes que sostienen el
valor probatorio del registro.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from pscnc.models.audit_trail import (
    AuditTrailItem,
    CryptographicEvidence,
    OtpLog,
    SigningStatus,
    TsaEvidence,
)


def _item_base(identidad, red, **overrides):  # type: ignore[no-untyped-def]
    ahora = datetime.now(UTC)
    transaccion = str(uuid.uuid4())
    datos = {
        **AuditTrailItem.build_keys(
            transaction_id=transaccion,
            national_id=identidad.national_id,
            b2b_client_id="aseguradora-py",
            created_at=ahora,
        ),
        "transaction_id": transaccion,
        "b2b_client_id": "aseguradora-py",
        "status": SigningStatus.INITIALIZED,
        "created_at": ahora,
        "identity_evidence": identidad,
        "network_evidence": red,
    }
    datos.update(overrides)
    return datos


def test_claves_derivadas_coherentes(identidad, red) -> None:  # type: ignore[no-untyped-def]
    item = AuditTrailItem(**_item_base(identidad, red))
    assert f"TX#{item.transaction_id}" == item.PK
    assert f"CI#PY-{identidad.national_id}" == item.GSI1PK
    assert item.GSI2PK == "CLIENT#aseguradora-py"


def test_rechaza_pk_inconsistente_con_transaction_id(identidad, red) -> None:  # type: ignore[no-untyped-def]
    datos = _item_base(identidad, red)
    datos["PK"] = f"TX#{uuid.uuid4()}"
    with pytest.raises(ValidationError, match="PK inconsistente"):
        AuditTrailItem(**datos)


def test_rechaza_gsi_de_otro_inquilino(identidad, red) -> None:  # type: ignore[no-untyped-def]
    datos = _item_base(identidad, red)
    datos["GSI2PK"] = "CLIENT#otro-banco"
    with pytest.raises(ValidationError, match="GSI2PK inconsistente"):
        AuditTrailItem(**datos)


def test_sesion_completada_exige_evidencia_criptografica(identidad, red, consentimiento) -> None:  # type: ignore[no-untyped-def]
    datos = _item_base(
        identidad,
        red,
        status=SigningStatus.SIGNING_COMPLETED,
        completed_at=datetime.now(UTC),
        consent_evidence=consentimiento,
    )
    with pytest.raises(ValidationError, match="evidencia criptográfica"):
        AuditTrailItem(**datos)


def test_rechaza_hashes_identicos() -> None:
    """Si el hash del firmado iguala al del original, la firma no se aplicó."""
    huella = "b" * 64
    with pytest.raises(ValidationError, match="no llegó a inyectarse"):
        CryptographicEvidence(
            original_pdf_sha256=huella,
            signed_pdf_sha256=huella,
            user_certificate_serial="01",
            ca_intermediate_serial="02",
            tsa_evidence=TsaEvidence(
                tsa_provider_name="TSA de pruebas",
                tsa_certificate_chain=["-----BEGIN CERTIFICATE-----"],
                rfc3161_response_base64="AAAA",
                timestamp_utc=datetime.now(UTC),
            ),
        )


def test_rechaza_otp_verificado_antes_de_enviarse() -> None:
    ahora = datetime.now(UTC)
    with pytest.raises(ValidationError, match="antes de haberse enviado"):
        OtpLog(
            channel_type="SMS",
            destination="+595981000000",
            otp_sent_timestamp=ahora,
            otp_verified_timestamp=ahora - timedelta(seconds=10),
            provider_message_id="msg-1",
            otp_code_hash="c" * 64,
        )


def test_rechaza_hash_de_otp_que_no_sea_sha256() -> None:
    ahora = datetime.now(UTC)
    with pytest.raises(ValidationError):
        OtpLog(
            channel_type="SMS",
            destination="+595981000000",
            otp_sent_timestamp=ahora,
            otp_verified_timestamp=ahora,
            provider_message_id="msg-1",
            otp_code_hash="481926",  # el código en claro jamás debe persistirse
        )
