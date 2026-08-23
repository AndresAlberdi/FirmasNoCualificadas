"""Prueba del flujo completo de la máquina de estados con dobles en memoria.

Sustituye DynamoDB, S3 y el módulo de onboarding por implementaciones en memoria,
pero conserva el motor criptográfico real. Verifica el contrato de negocio:
qué se persiste, en qué orden y qué se rechaza.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest

from pscnc.compliance.legal_guard import LegalGuard
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority
from pscnc.crypto.pades import PadesSigner
from pscnc.crypto.tsa import RecordingTimeStamper
from pscnc.errors import (
    BiometricThresholdError,
    ConsentVerificationError,
    InvalidSessionStateError,
    LegallyExcludedDocumentError,
    TenantMismatchError,
)
from pscnc.models.api import ConfirmSignatureRequest
from pscnc.models.audit_trail import AuditTrailItem, SigningStatus
from pscnc.onboarding.client import SandboxOnboardingClient
from pscnc.orchestrator.state_machine import RequestEnvironment, SigningService
from pscnc.repositories.dynamo_audit import SecurityContext

pytestmark = pytest.mark.integration

INQUILINO = "aseguradora-py"


# --------------------------------------------------------------------- Dobles
class RepositorioEnMemoria:
    def __init__(self) -> None:
        self.versiones: dict[str, list[AuditTrailItem]] = {}

    def put_new_version(self, item: AuditTrailItem, context: SecurityContext) -> None:
        context.assert_owns(item.b2b_client_id)
        historial = self.versiones.setdefault(item.transaction_id, [])
        if any(v.SK == item.SK for v in historial):
            raise AssertionError("La evidencia no debe sobrescribirse")
        historial.append(item)

    def get_latest(self, transaction_id: str, context: SecurityContext) -> AuditTrailItem:
        historial = self.versiones[transaction_id]
        item = historial[-1]
        context.assert_owns(item.b2b_client_id)
        return item

    def next_version_key(self, transaction_id: str) -> int:
        return len(self.versiones.get(transaction_id, [])) + 1


class BovedaEnMemoria:
    def __init__(self) -> None:
        self.objetos: dict[str, bytes] = {}

    @staticmethod
    def signed_key(t: str, x: str) -> str:
        return f"{t}/{x}/documento-firmado.pdf"

    @staticmethod
    def evidence_key(t: str, x: str) -> str:
        return f"{t}/{x}/expediente-evidencias.pdf"

    @staticmethod
    def original_key(t: str, x: str) -> str:
        return f"{t}/{x}/documento-original.pdf"

    def put_original_document(self, *, b2b_client_id, transaction_id, content, sha256):  # type: ignore[no-untyped-def]
        self.objetos[self.original_key(b2b_client_id, transaction_id)] = content

    def get_original_document(self, *, b2b_client_id, transaction_id):  # type: ignore[no-untyped-def]
        return self.objetos[self.original_key(b2b_client_id, transaction_id)]

    def put_signed_document(self, *, b2b_client_id, transaction_id, content, sha256):  # type: ignore[no-untyped-def]
        self.objetos[self.signed_key(b2b_client_id, transaction_id)] = content

    def put_evidence_report(self, *, b2b_client_id, transaction_id, content, sha256):  # type: ignore[no-untyped-def]
        self.objetos[self.evidence_key(b2b_client_id, transaction_id)] = content

    def presigned_signed_document(self, t: str, x: str) -> str:
        return f"https://s3.local/{self.signed_key(t, x)}?X-Amz-Expires=300"

    def presigned_evidence_report(self, t: str, x: str) -> str:
        return f"https://s3.local/{self.evidence_key(t, x)}?X-Amz-Expires=300"


def _pdf(texto: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    lienzo = canvas.Canvas(buffer, pagesize=A4)
    lienzo.drawString(72, 760, texto)
    lienzo.showPage()
    lienzo.save()
    return buffer.getvalue()


# ------------------------------------------------------------------ Fixtures
@pytest.fixture()
def servicio(ca_certificate_der, ca_signer):  # type: ignore[no-untyped-def]
    from asn1crypto import keys as ak
    from asn1crypto import x509 as ax
    from cryptography import x509 as cx
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
    from pyhanko.sign.timestamps import DummyTimeStamper

    clave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nombre = cx.Name([cx.NameAttribute(NameOID.COMMON_NAME, "TSA de Pruebas")])
    ahora = datetime.now(UTC)
    cert = (
        cx.CertificateBuilder()
        .subject_name(nombre)
        .issuer_name(nombre)
        .public_key(clave.public_key())
        .serial_number(cx.random_serial_number())
        .not_valid_before(ahora - timedelta(days=1))
        .not_valid_after(ahora + timedelta(days=365))
        .add_extension(cx.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]), critical=True)
        .sign(clave, hashes.SHA256())
    )
    tsa_cert = ax.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
    tsa_key = ak.PrivateKeyInfo.load(
        clave.private_bytes(
            serialization.Encoding.DER,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )

    autoridad = EphemeralCertificateAuthority(
        ca_certificate_der=ca_certificate_der,
        ca_signer=ca_signer,
        crl_url="https://crl.pruebas.example.py/pscnc/intermediate.crl",
    )
    firmante = PadesSigner(
        certificate_authority=autoridad,
        timestamper_factory=lambda: RecordingTimeStamper(
            "",
            provider_name="TSA de Pruebas",
            delegate=DummyTimeStamper(tsa_cert=tsa_cert, tsa_key=tsa_key),
        ),
    )

    repositorio = RepositorioEnMemoria()
    boveda = BovedaEnMemoria()
    servicio = SigningService(
        repository=repositorio,  # type: ignore[arg-type]
        vault=boveda,  # type: ignore[arg-type]
        onboarding=SandboxOnboardingClient(),
        certificate_authority=autoridad,
        signer=firmante,
        legal_guard=LegalGuard(),
    )
    return servicio, repositorio, boveda


@pytest.fixture()
def contexto() -> SecurityContext:
    return SecurityContext(b2b_client_id=INQUILINO, principal="hmac:pruebas")


@pytest.fixture()
def entorno() -> RequestEnvironment:
    return RequestEnvironment(
        client_ip="190.104.128.5", source_port=51234, user_agent="pruebas/1.0"
    )


def _confirmacion() -> ConfirmSignatureRequest:
    return ConfirmSignatureRequest(
        consent_otp_code=SandboxOnboardingClient.OTP_ACEPTADO,
        consent_statement="Acepto firmar electronicamente el documento identificado.",
        visual_signature_enabled=False,
    )


# ------------------------------------------------------------------ Pruebas
def test_flujo_completo_persiste_evidencia_y_documentos(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    svc, repositorio, boveda = servicio

    sesion = svc.create_session(
        context=contexto,
        onboarding_token="onb-1",
        pdf_document=_pdf("Contrato de servicios de consultoria"),
        filename="contrato.pdf",
        environment=entorno,
    )
    assert sesion.status is SigningStatus.INITIALIZED
    assert len(sesion.original_document_hash) == 64

    completado = svc.confirm(
        context=contexto, transaction_id=sesion.signing_session_id, payload=_confirmacion()
    )
    assert completado.status is SigningStatus.SIGNING_COMPLETED
    assert completado.signed_document_hash != sesion.original_document_hash
    assert completado.timestamp.authority == "TSA de Pruebas"

    # Dos versiones: la apertura y el cierre. La primera no se sobrescribe.
    historial = repositorio.versiones[sesion.signing_session_id]
    assert [v.SK for v in historial] == ["METADATA#V1", "METADATA#V2"]
    assert historial[0].status is SigningStatus.INITIALIZED
    assert historial[1].cryptographic_evidence is not None
    assert historial[1].consent_evidence is not None

    # El expediente y el documento firmado quedan en la bóveda.
    assert boveda.objetos[BovedaEnMemoria.evidence_key(INQUILINO, sesion.signing_session_id)]
    assert boveda.objetos[
        BovedaEnMemoria.signed_key(INQUILINO, sesion.signing_session_id)
    ].startswith(b"%PDF-")

    paquete = svc.evidence(context=contexto, transaction_id=sesion.signing_session_id)
    assert paquete.signed_document_url is not None
    assert paquete.evidence_report_url is not None
    assert paquete.verifications.identity_match_approved is True


def test_expediente_de_evidencias_es_un_pdf_legible(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    from pypdf import PdfReader

    svc, _, boveda = servicio
    sesion = svc.create_session(
        context=contexto,
        onboarding_token="onb-2",
        pdf_document=_pdf("Contrato de servicios"),
        filename="contrato.pdf",
        environment=entorno,
    )
    svc.confirm(context=contexto, transaction_id=sesion.signing_session_id, payload=_confirmacion())

    expediente = boveda.objetos[BovedaEnMemoria.evidence_key(INQUILINO, sesion.signing_session_id)]
    lector = PdfReader(io.BytesIO(expediente))
    texto = "\n".join(pagina.extract_text() or "" for pagina in lector.pages)

    assert "Expediente de Evidencias" in texto
    assert "PAdES-B-T" in texto
    assert "6822" in texto  # cita de la ley aplicable


def test_bloquea_documento_legalmente_excluido(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    svc, repositorio, _ = servicio
    with pytest.raises(LegallyExcludedDocumentError):
        svc.create_session(
            context=contexto,
            onboarding_token="onb-3",
            pdf_document=_pdf("Constituyese HIPOTECA sobre el inmueble de referencia"),
            filename="hipoteca.pdf",
            environment=entorno,
        )
    assert repositorio.versiones == {}  # no se abre sesión ni se registra nada


def test_rechaza_biometria_insuficiente(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    svc, _, _ = servicio
    svc._min_score = 0.999  # umbral por encima del puntaje sintético (0.985)
    with pytest.raises(BiometricThresholdError):
        svc.create_session(
            context=contexto,
            onboarding_token="onb-4",
            pdf_document=_pdf("Contrato ordinario"),
            filename="c.pdf",
            environment=entorno,
        )


def test_rechaza_otp_incorrecto(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    svc, _, _ = servicio
    sesion = svc.create_session(
        context=contexto,
        onboarding_token="onb-5",
        pdf_document=_pdf("Contrato ordinario"),
        filename="c.pdf",
        environment=entorno,
    )
    payload = _confirmacion().model_copy(update={"consent_otp_code": "999999"})
    with pytest.raises(ConsentVerificationError):
        svc.confirm(context=contexto, transaction_id=sesion.signing_session_id, payload=payload)


def test_no_admite_doble_firma(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    svc, _, _ = servicio
    sesion = svc.create_session(
        context=contexto,
        onboarding_token="onb-6",
        pdf_document=_pdf("Contrato ordinario"),
        filename="c.pdf",
        environment=entorno,
    )
    svc.confirm(context=contexto, transaction_id=sesion.signing_session_id, payload=_confirmacion())
    with pytest.raises(InvalidSessionStateError, match="ya fue firmada"):
        svc.confirm(
            context=contexto, transaction_id=sesion.signing_session_id, payload=_confirmacion()
        )


def test_otro_inquilino_no_accede_a_la_transaccion(servicio, contexto, entorno) -> None:  # type: ignore[no-untyped-def]
    """Verificación estructural del aislamiento multi-tenant (ADR-0005)."""
    svc, _, _ = servicio
    sesion = svc.create_session(
        context=contexto,
        onboarding_token="onb-7",
        pdf_document=_pdf("Contrato ordinario"),
        filename="c.pdf",
        environment=entorno,
    )
    intruso = SecurityContext(b2b_client_id="banco-intruso")
    with pytest.raises(TenantMismatchError):
        svc.evidence(context=intruso, transaction_id=sesion.signing_session_id)
