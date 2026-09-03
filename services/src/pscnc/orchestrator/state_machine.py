"""Máquina de estados de la sesión de firma (Agente Coordinador).

    INITIALIZED ──confirm()──► SIGNING_COMPLETED
         │
         ├──expiración──► FAILED
         └──error────────► FAILED

Reglas que gobiernan las transiciones:

* Solo se firma si el onboarding está ``APPROVED``, la biometría supera el umbral
  declarado en la DPSC y hay prueba de vida.
* Solo se firma si el Agente de Cumplimiento no detecta un acto jurídico excluido.
* Si el sellado de tiempo falla, la transacción falla completa.
* Si la evidencia no se persiste, el documento firmado **no se entrega**: un
  documento firmado sin pista de auditoría es un pasivo, no un activo.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jurisdictions import DEFAULT_JURISDICTION, get_profile
from pscnc.compliance.legal_guard import LegalGuard, enforce_biometric_threshold
from pscnc.crypto.ephemeral_ca import EphemeralCertificateAuthority, SubjectData
from pscnc.crypto.pades import PadesSigner, VisualSignatureSpec, sha256_hex
from pscnc.errors import (
    InvalidSessionStateError,
    SessionExpiredError,
)
from pscnc.logging_setup import get_logger
from pscnc.models.api import (
    ConfirmSignatureRequest,
    EvidenceBundle,
    SigningSessionCompleted,
    SigningSessionCreated,
    TimestampInfo,
    VerificationSummary,
)
from pscnc.models.audit_trail import (
    AuditTrailItem,
    ConsentEvidence,
    CryptographicEvidence,
    NetworkEvidence,
    SigningStatus,
    TsaEvidence,
)
from pscnc.onboarding.client import OnboardingClient
from pscnc.repositories.dynamo_audit import AuditTrailRepository, SecurityContext
from pscnc.repositories.s3_vault import DocumentVault

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class RequestEnvironment:
    """Datos de red capturados de la petición, con valor pericial."""

    client_ip: str
    source_port: int
    user_agent: str
    tls_version: str = "TLSv1.3"
    tls_cipher: str = "TLS_AES_256_GCM_SHA384"


class SigningService:
    """Orquesta el ciclo completo de una sesión de firma."""

    def __init__(
        self,
        *,
        repository: AuditTrailRepository,
        vault: DocumentVault,
        onboarding: OnboardingClient,
        certificate_authority: EphemeralCertificateAuthority,
        signer: PadesSigner,
        legal_guard: LegalGuard,
        min_facial_match_score: float = 0.95,
        session_ttl_minutes: int = 60,
        presigned_ttl: int = 300,
        jurisdiction: str = DEFAULT_JURISDICTION,
    ) -> None:
        self._repo = repository
        self._vault = vault
        self._onboarding = onboarding
        self._ca = certificate_authority
        self._signer = signer
        self._guard = legal_guard
        self._min_score = min_facial_match_score
        self._ttl = timedelta(minutes=session_ttl_minutes)
        self._presigned_ttl = presigned_ttl
        self._jurisdiction = jurisdiction.upper()

    # ------------------------------------------------------- Inicialización --
    def create_session(
        self,
        *,
        context: SecurityContext,
        onboarding_token: str,
        pdf_document: bytes,
        filename: str | None,
        environment: RequestEnvironment,
        client_metadata: dict[str, str] | None = None,
    ) -> SigningSessionCreated:
        """Valida las precondiciones, resguarda el original y abre la sesión."""
        transaction_id = str(uuid.uuid4())
        ahora = datetime.now(UTC)

        instantanea = self._onboarding.fetch(onboarding_token)
        identidad = instantanea.identity

        enforce_biometric_threshold(
            identidad.facial_match_score,
            minimum=self._min_score,
            liveness_detected=identidad.liveness_detected,
            transaction_id=transaction_id,
        )

        veredicto = self._guard.evaluate_pdf(pdf_document)
        self._guard.enforce(veredicto, transaction_id=transaction_id)

        hash_original = sha256_hex(pdf_document)
        self._vault.put_original_document(
            b2b_client_id=context.b2b_client_id,
            transaction_id=transaction_id,
            content=pdf_document,
            sha256=hash_original,
        )

        metadatos = dict(client_metadata or {})
        metadatos["onboarding_id"] = instantanea.onboarding_id
        if veredicto.requires_human_review:
            metadatos["compliance_review"] = "recomendada"
        if not veredicto.text_extraction_succeeded:
            metadatos["compliance_text_extraction"] = "fallida"

        item = AuditTrailItem(
            **AuditTrailItem.build_keys(
                transaction_id=transaction_id,
                national_id=identidad.national_id,
                b2b_client_id=context.b2b_client_id,
                created_at=ahora,
                version=1,
                jurisdiction=self._jurisdiction,
            ),
            transaction_id=transaction_id,
            b2b_client_id=context.b2b_client_id,
            jurisdiction=self._jurisdiction,
            status=SigningStatus.INITIALIZED,
            created_at=ahora,
            document_filename=filename,
            client_metadata=metadatos,
            identity_evidence=identidad,
            network_evidence=NetworkEvidence(
                client_ip=environment.client_ip,
                source_port=environment.source_port,
                user_agent=environment.user_agent,
                tls_version=environment.tls_version,
                tls_cipher=environment.tls_cipher,
            ),
        )
        # El hash del original queda en los metadatos hasta que exista la evidencia
        # criptográfica completa, que exige también el hash del documento firmado.
        item.client_metadata["original_pdf_sha256"] = hash_original

        self._repo.put_new_version(item, context)

        logger.info(
            "signing_session_created",
            transaction_id=transaction_id,
            b2b_client_id=context.b2b_client_id,
            original_sha256=hash_original,
        )

        return SigningSessionCreated(
            signing_session_id=transaction_id,
            status=SigningStatus.INITIALIZED,
            original_document_hash=hash_original,
            created_at=ahora,
            expires_at=ahora + self._ttl,
        )

    # ------------------------------------------------------------ Confirmar --
    def confirm(
        self,
        *,
        context: SecurityContext,
        transaction_id: str,
        payload: ConfirmSignatureRequest,
    ) -> SigningSessionCompleted:
        """Verifica el consentimiento, firma el documento y sella la evidencia."""
        item = self._repo.get_latest(transaction_id, context)
        ahora = datetime.now(UTC)

        if item.status is SigningStatus.SIGNING_COMPLETED:
            raise InvalidSessionStateError("La sesión ya fue firmada")
        if item.status is not SigningStatus.INITIALIZED:
            raise InvalidSessionStateError(
                f"La sesión no admite la firma en su estado actual: {item.status.value}"
            )
        if ahora - item.created_at.replace(tzinfo=item.created_at.tzinfo or UTC) > self._ttl:
            raise SessionExpiredError("La sesión de firma expiró; debe iniciarse una nueva")

        onboarding_id = item.client_metadata.get("onboarding_id", "")
        otp = self._onboarding.verify_otp(onboarding_id, payload.consent_otp_code)

        consentimiento = ConsentEvidence(
            explicit_consent_checked=True,
            consent_statement=payload.consent_statement,
            consent_statement_sha256=hashlib.sha256(
                payload.consent_statement.encode("utf-8")
            ).hexdigest(),
            otp_channels=[otp],
        )

        original = self._vault.get_original_document(
            b2b_client_id=context.b2b_client_id, transaction_id=transaction_id
        )
        hash_original_declarado = item.client_metadata.get("original_pdf_sha256", "")
        if hash_original_declarado and sha256_hex(original) != hash_original_declarado:
            # El original recuperado no coincide con el registrado al abrir la sesión.
            raise InvalidSessionStateError(
                "El documento original almacenado no coincide con su huella registrada"
            )

        resultado = self._signer.sign(
            original,
            SubjectData.for_jurisdiction(
                get_profile(item.jurisdiction),
                # Acá nada se adivina: la evidencia de identidad guarda el nombre y
                # el apellido por separado desde el primer día, porque es lo que
                # devuelve la verificación documental (ADR-0010).
                given_name=item.identity_evidence.first_name,
                surname=item.identity_evidence.last_name,
                national_id=item.identity_evidence.national_id,
                document_type=item.identity_evidence.document_type,
                transaction_id=transaction_id,
            ),
            visual=VisualSignatureSpec(
                enabled=payload.visual_signature_enabled,
                page=payload.signature_page,
                x=payload.signature_coordinate_x,
                y=payload.signature_coordinate_y,
                width=payload.signature_width,
                height=payload.signature_height,
            ),
        )

        cripto = CryptographicEvidence(
            original_pdf_sha256=resultado.original_sha256,
            signed_pdf_sha256=resultado.signed_sha256,
            user_certificate_serial=resultado.certificate.serial_number,
            user_certificate_pem=resultado.certificate.certificate_pem,
            ca_intermediate_serial=self._ca.ca_serial_number,
            signature_format="PAdES-B-T",
            tsa_evidence=TsaEvidence(
                tsa_provider_name=resultado.timestamp.provider_name,
                tsa_certificate_chain=resultado.timestamp.certificate_chain_pem,
                rfc3161_response_base64=resultado.timestamp.token_base64,
                timestamp_utc=resultado.timestamp.gen_time,
                tsa_serial_number=resultado.timestamp.serial_number,
            ),
        )

        # Orden deliberado: primero se consolida la evidencia, después se publica
        # el documento firmado. Si la evidencia falla, no hay entrega.
        version = self._repo.next_version_key(transaction_id)
        completado = item.model_copy(
            update={
                **AuditTrailItem.build_keys(
                    transaction_id=transaction_id,
                    national_id=item.identity_evidence.national_id,
                    b2b_client_id=item.b2b_client_id,
                    created_at=item.created_at,
                    version=version,
                    jurisdiction=item.jurisdiction,
                ),
                "status": SigningStatus.SIGNING_COMPLETED,
                "completed_at": ahora,
                "consent_evidence": consentimiento,
                "cryptographic_evidence": cripto,
                "signed_document_key": DocumentVault.signed_key(
                    context.b2b_client_id, transaction_id
                ),
                "evidence_report_key": DocumentVault.evidence_key(
                    context.b2b_client_id, transaction_id
                ),
            }
        )
        # Revalidación completa del ítem antes de persistir.
        completado = AuditTrailItem.model_validate(completado.model_dump())

        from pscnc.evidence.report import build_evidence_report

        expediente = build_evidence_report(completado)

        self._vault.put_evidence_report(
            b2b_client_id=context.b2b_client_id,
            transaction_id=transaction_id,
            content=expediente,
            sha256=sha256_hex(expediente),
        )
        self._repo.put_new_version(completado, context)
        self._vault.put_signed_document(
            b2b_client_id=context.b2b_client_id,
            transaction_id=transaction_id,
            content=resultado.signed_pdf,
            sha256=resultado.signed_sha256,
        )

        logger.info(
            "signing_session_completed",
            transaction_id=transaction_id,
            b2b_client_id=context.b2b_client_id,
            signed_sha256=resultado.signed_sha256,
            tsa_provider=resultado.timestamp.provider_name,
        )

        return SigningSessionCompleted(
            signing_session_id=transaction_id,
            status=SigningStatus.SIGNING_COMPLETED,
            signed_document_hash=resultado.signed_sha256,
            user_certificate_serial=resultado.certificate.serial_number,
            signature_format="PAdES-B-T",
            timestamp=TimestampInfo(
                authority=resultado.timestamp.provider_name,
                serial=resultado.timestamp.serial_number,
                time=resultado.timestamp.gen_time,
            ),
        )

    # ------------------------------------------------------------ Evidencia --
    def evidence(self, *, context: SecurityContext, transaction_id: str) -> EvidenceBundle:
        """Devuelve el paquete de evidencias con URLs de descarga temporales."""
        item = self._repo.get_latest(transaction_id, context)
        identidad = item.identity_evidence

        firmado_url = None
        evidencia_url = None
        if item.status is SigningStatus.SIGNING_COMPLETED:
            firmado_url = self._vault.presigned_signed_document(
                context.b2b_client_id, transaction_id
            )
            evidencia_url = self._vault.presigned_evidence_report(
                context.b2b_client_id, transaction_id
            )

        return EvidenceBundle(
            signing_session_id=transaction_id,
            status=item.status,
            signed_document_url=firmado_url,
            evidence_report_url=evidencia_url,
            url_expires_in_seconds=self._presigned_ttl,
            original_document_hash=(
                item.cryptographic_evidence.original_pdf_sha256
                if item.cryptographic_evidence
                else item.client_metadata.get("original_pdf_sha256", "")
            ),
            signed_document_hash=(
                item.cryptographic_evidence.signed_pdf_sha256
                if item.cryptographic_evidence
                else None
            ),
            verifications=VerificationSummary(
                aml_pep_checked=identidad.aml_pep_checked,
                biometric_score=identidad.facial_match_score,
                liveness_detected=identidad.liveness_detected,
                identity_match_approved=identidad.facial_match_score >= self._min_score,
            ),
        )
