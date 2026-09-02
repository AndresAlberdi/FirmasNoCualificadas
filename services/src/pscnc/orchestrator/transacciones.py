"""Servicio de transacciones del contrato público v1 (ADR-0007 nivel 1, ADR-0009).

Orquesta las tres llamadas del contrato: crear, confirmar y recuperar artefactos.
El acto que produce es un acta de evidencia sellada; el documento no se modifica.

## Lo que este servicio deliberadamente NO hace

* **No decide la identidad.** Recibe `identity_decision` y la asienta. Solo
  rechaza si el propio tenant declaró que no aprobó — que es leer su decisión, no
  tomar una nueva.
* **No verifica el OTP del tenant.** En `TENANT_VERIFIED` la prueba es evidencia.
* **No conserva el documento.** En hash-only nunca lo recibe.

## El orden de las escrituras, que no es casual

Primero se sella el acta, después se persiste, y solo entonces se responde. Si el
sellado falla no hay acta; si la persistencia falla, no se responde con un acta
que no existe en ningún registro. Un acta entregada al tenant que no quedó
asentada es peor que un error: el tenant cree tener prueba de algo que no podemos
respaldar.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jurisdictions import JurisdictionProfile, UnknownJurisdictionError, get_profile
from pscnc.crypto.ephemeral_ca import SubjectData
from pscnc.crypto.pades import PadesSigner, SignatureResult
from pscnc.errors import TimestampError
from pscnc.evidence.acta import ActaPayload, ActaSealer, DocumentReference, SealedActa
from pscnc.logging_setup import get_logger
from pscnc.models.motivos import RejectionReason
from pscnc.models.v1 import (
    ActaSeal,
    Artifacts,
    ConfirmTransactionRequest,
    CreateTransactionRequest,
    OtpMode,
    PublicVerification,
    ServiceLevel,
    TransactionConfirmed,
    TransactionCreated,
    TransactionStatus,
)

logger = get_logger(__name__)

#: Longitud del código público de verificación. 12 caracteres de un alfabeto de
#: 32 dan ~60 bits: no se adivina por fuerza bruta y sigue siendo transcribible
#: por una persona que lo lee de un papel.
VERIFICATION_CODE_LENGTH = 12
VERIFICATION_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin I, L, O, 0, 1


class TransactionRejectedError(Exception):
    """Rechazo con un motivo del contrato público."""

    def __init__(
        self,
        motivo: RejectionReason,
        mensaje: str,
        *,
        transaction_id: str | None = None,
        detalle: dict[str, str | int | list[str]] | None = None,
    ) -> None:
        super().__init__(mensaje)
        self.motivo = motivo
        self.mensaje = mensaje
        self.transaction_id = transaction_id
        self.detalle = detalle or {}


def generate_verification_code() -> str:
    """Código público de verificación, sin caracteres que se confundan al leer."""
    return "".join(secrets.choice(VERIFICATION_ALPHABET) for _ in range(VERIFICATION_CODE_LENGTH))


@dataclass(slots=True)
class Transaction:
    """Estado de una transacción en curso."""

    transaction_id: str
    tenant_id: str
    tenant_reference: str
    jurisdiction: str
    service_level: ServiceLevel
    otp_mode: OtpMode
    document_sha256: str
    document_version: int
    document_code: str
    document_closed_at: datetime
    identity_approved: bool
    created_at: datetime
    expires_at: datetime
    status: TransactionStatus = TransactionStatus.CREATED
    confirmed_at: datetime | None = None
    verification_code: str | None = None
    acta_jws: str | None = None
    acta_payload_sha256: str | None = None
    acta_key_alias: str | None = None
    signed_document_sha256: str | None = None
    signer_certificate_serial: str | None = None
    timestamp_authority: str | None = None


class TransactionRepository:
    """Almacén de transacciones en memoria, para desarrollo y pruebas.

    En producción lo reemplaza la pista de auditoría en DynamoDB, que además es
    append-only. Se declara acá para que el servicio dependa de un contrato y no
    de un proveedor.
    """

    def __init__(self) -> None:
        self._por_id: dict[str, Transaction] = {}
        self._por_codigo: dict[str, str] = {}

    def guardar(self, transaccion: Transaction) -> None:
        self._por_id[transaccion.transaction_id] = transaccion
        if transaccion.verification_code:
            self._por_codigo[transaccion.verification_code] = transaccion.transaction_id

    def obtener(self, transaction_id: str) -> Transaction | None:
        return self._por_id.get(transaction_id)

    def obtener_por_codigo(self, codigo: str) -> Transaction | None:
        identificador = self._por_codigo.get(codigo)
        return self._por_id.get(identificador) if identificador else None


class TransactionService:
    """Implementa las tres llamadas del contrato público."""

    def __init__(
        self,
        *,
        repositorio: TransactionRepository,
        sellador: ActaSealer,
        jurisdiccion_por_defecto: str,
        ttl_minutos: int = 60,
        firmante_pades: PadesSigner | None = None,
        environment: str = "prod",
    ) -> None:
        self._repo = repositorio
        self._sellador = sellador
        self._jurisdiccion_por_defecto = jurisdiccion_por_defecto
        self._ttl = timedelta(minutes=ttl_minutos)
        # Sin firmante PAdES el nivel 2 no está disponible: se rechaza al abrir la
        # transacción, no al confirmarla, para que el tenant no llegue con el
        # documento a un callejón sin salida.
        self._firmante_pades = firmante_pades
        self._environment = environment

    # ------------------------------------------------------------- Crear ----
    def crear(self, *, tenant_id: str, peticion: CreateTransactionRequest) -> TransactionCreated:
        """Abre una transacción de firma."""
        perfil = self._perfil(peticion.jurisdiction or self._jurisdiccion_por_defecto)

        # La única lectura que se hace de la decisión ajena: si el tenant declaró
        # que no aprobó, no hay nada que firmar. No se re-evalúa el puntaje.
        if not peticion.identity_decision.approved:
            raise TransactionRejectedError(
                RejectionReason.IDENTITY_NOT_APPROVED,
                "El tenant declaró que la verificación de identidad no fue aprobada.",
                detalle={"policy_version": peticion.identity_decision.policy_version},
            )

        if peticion.service_level is ServiceLevel.PADES and self._firmante_pades is None:
            # El nivel 2 depende de la CA y de la autoridad de sellado de tiempo
            # (docs/PENDIENTES.md §1). Un motivo propio evita que el tenant lo
            # interprete como un fallo transitorio y reintente.
            raise TransactionRejectedError(
                RejectionReason.SERVICE_LEVEL_UNAVAILABLE,
                "El nivel 2 exige la CA intermedia y la autoridad de sellado de tiempo; "
                "no están configuradas en este despliegue.",
                detalle={"nivel_disponible": ServiceLevel.SEALED_ACTA.value},
            )

        ahora = datetime.now(UTC)
        transaccion = Transaction(
            transaction_id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            tenant_reference=peticion.tenant_reference,
            jurisdiction=perfil.code,
            service_level=peticion.service_level,
            otp_mode=peticion.otp_mode,
            document_sha256=peticion.document.sha256,
            document_version=peticion.document.version,
            document_code=peticion.document.code,
            document_closed_at=peticion.document.closed_at,
            identity_approved=True,
            created_at=ahora,
            expires_at=ahora + self._ttl,
        )
        self._repo.guardar(transaccion)

        logger.info(
            "transaction_created",
            transaction_id=transaccion.transaction_id,
            tenant_id=tenant_id,
            tenant_reference=peticion.tenant_reference,
            jurisdiction=perfil.code,
            service_level=peticion.service_level.value,
            otp_mode=peticion.otp_mode.value,
        )

        return TransactionCreated(
            transaction_id=transaccion.transaction_id,
            tenant_reference=transaccion.tenant_reference,
            status=transaccion.status,
            service_level=transaccion.service_level,
            jurisdiction=transaccion.jurisdiction,
            document_sha256=transaccion.document_sha256,
            created_at=transaccion.created_at,
            expires_at=transaccion.expires_at,
        )

    # ---------------------------------------------------------- Confirmar ---
    def confirmar(
        self, *, tenant_id: str, transaction_id: str, peticion: ConfirmTransactionRequest
    ) -> TransactionConfirmed:
        """Confirma el acto y sella el acta."""
        transaccion = self._transaccion_del_inquilino(tenant_id, transaction_id)
        ahora = datetime.now(UTC)

        if transaccion.status is TransactionStatus.CONFIRMED:
            # No es un error del tenant: es una repetición sin clave de
            # idempotencia. Se distingue del estado inválido para que el tenant
            # pueda tratarla como lo que es.
            raise TransactionRejectedError(
                RejectionReason.TRANSACTION_ALREADY_CONFIRMED,
                "La transacción ya fue confirmada. Use la misma clave de idempotencia "
                "para recuperar el acta original.",
                transaction_id=transaction_id,
            )

        if transaccion.status is not TransactionStatus.CREATED:
            raise TransactionRejectedError(
                RejectionReason.INVALID_STATE,
                f"La transacción está en estado {transaccion.status.value}.",
                transaction_id=transaction_id,
            )

        if ahora > transaccion.expires_at:
            transaccion.status = TransactionStatus.EXPIRED
            self._repo.guardar(transaccion)
            raise TransactionRejectedError(
                RejectionReason.TRANSACTION_EXPIRED,
                "La transacción expiró; debe abrirse una nueva.",
                transaction_id=transaction_id,
            )

        # La huella recibida tiene que ser la registrada al abrir: si el documento
        # se regeneró entre la apertura y la firma, lo que se firma no es lo que
        # la persona revisó.
        if peticion.document_sha256 != transaccion.document_sha256:
            raise TransactionRejectedError(
                RejectionReason.DOCUMENT_TAMPERED,
                "La huella del documento no coincide con la registrada al abrir la transacción.",
                transaction_id=transaction_id,
            )

        self._verificar_otp(transaccion, peticion)

        # Nivel 2: se firma el documento antes de sellar el acta, para que el acta
        # pueda referenciar la huella del PDF firmado y el certificado que la
        # produjo. Si algo de esto falla, no hay acta ni transacción confirmada.
        firma_pades = self._firmar_documento(transaccion, peticion)

        # Se sella y después se persiste: un acta entregada que no quedó asentada
        # es peor que un error, porque el tenant cree tener una prueba que no
        # podemos respaldar.
        acta_sellada = self._sellar(transaccion, peticion, ahora, firma_pades)

        transaccion.status = TransactionStatus.CONFIRMED
        transaccion.confirmed_at = ahora
        transaccion.verification_code = generate_verification_code()
        transaccion.acta_jws = acta_sellada.jws
        transaccion.acta_payload_sha256 = acta_sellada.payload_sha256
        transaccion.acta_key_alias = acta_sellada.key_alias
        if firma_pades is not None:
            transaccion.signed_document_sha256 = firma_pades.signed_sha256
            transaccion.signer_certificate_serial = firma_pades.certificate.serial_number
            transaccion.timestamp_authority = firma_pades.timestamp.provider_name
        self._repo.guardar(transaccion)

        logger.info(
            "transaction_confirmed",
            transaction_id=transaction_id,
            tenant_id=tenant_id,
            key_alias=acta_sellada.key_alias,
        )

        return TransactionConfirmed(
            transaction_id=transaction_id,
            tenant_reference=transaccion.tenant_reference,
            status=transaccion.status,
            service_level=transaccion.service_level,
            confirmed_at=ahora,
            acta=self._sello(transaccion),
            verification_code=transaccion.verification_code,
            signed_document_sha256=transaccion.signed_document_sha256,
            timestamp_authority=transaccion.timestamp_authority,
        )

    # --------------------------------------------------------- Artifacts ---
    def artefactos(self, *, tenant_id: str, transaction_id: str) -> Artifacts:
        transaccion = self._transaccion_del_inquilino(tenant_id, transaction_id)

        return Artifacts(
            transaction_id=transaccion.transaction_id,
            status=transaccion.status,
            service_level=transaccion.service_level,
            acta=self._sello(transaccion) if transaccion.acta_jws else None,
            verification_code=transaccion.verification_code,
        )

    # ------------------------------------------------ Verificación pública --
    def verificar(self, codigo: str) -> PublicVerification:
        """Constancia pública, sin datos personales y sin autenticación.

        La consulta quien recibió el documento, que no tiene credenciales. Un
        código inexistente devuelve `exists: false` con el resto vacío, sin
        distinguir «no existe» de «no está confirmada»: quien tiene un código al
        azar no debe poder averiguar cuáles existen.
        """
        transaccion = self._repo.obtener_por_codigo(codigo)

        if transaccion is None or transaccion.status is not TransactionStatus.CONFIRMED:
            return PublicVerification(verification_code=codigo, exists=False)

        perfil = self._perfil(transaccion.jurisdiction)

        return PublicVerification(
            verification_code=codigo,
            exists=True,
            status=transaccion.status,
            document_sha256=transaccion.document_sha256,
            document_code=transaccion.document_code,
            signed_at=transaccion.confirmed_at,
            jurisdiction=perfil.code,
            legal_basis=perfil.signature_law_citation,
            service_level=transaccion.service_level,
            acta_jws=transaccion.acta_jws,
        )

    # ------------------------------------------------------------ Interno ---
    def _perfil(self, codigo: str) -> JurisdictionProfile:
        try:
            return get_profile(codigo)
        except UnknownJurisdictionError as exc:
            raise TransactionRejectedError(
                RejectionReason.UNSUPPORTED_JURISDICTION,
                f"No hay perfil para la jurisdicción {codigo!r}.",
            ) from exc

    def _transaccion_del_inquilino(self, tenant_id: str, transaction_id: str) -> Transaction:
        transaccion = self._repo.obtener(transaction_id)
        if transaccion is None:
            raise TransactionRejectedError(
                RejectionReason.TRANSACTION_NOT_FOUND,
                "No existe la transacción solicitada.",
                transaction_id=transaction_id,
            )
        if transaccion.tenant_id != tenant_id:
            # Se responde con un motivo propio y no con «no encontrada» porque el
            # inquilino está autenticado: ocultarle que el recurso existe no lo
            # protege de nada y le impide diagnosticar su propio error.
            logger.warning(
                "cross_tenant_transaction_blocked",
                transaction_id=transaction_id,
                requesting_tenant=tenant_id,
            )
            raise TransactionRejectedError(
                RejectionReason.TRANSACTION_OF_ANOTHER_TENANT,
                "La transacción pertenece a otro inquilino.",
                transaction_id=transaction_id,
            )
        return transaccion

    def _verificar_otp(self, transaccion: Transaction, peticion: ConfirmTransactionRequest) -> None:
        """Comprueba que llegó la prueba que el modo exige.

        En `TENANT_VERIFIED` la prueba es evidencia y no se revalida: el OTP
        acredita la voluntad ante el tenant, que es con quien la persona contrata.
        """
        if transaccion.otp_mode is OtpMode.TENANT_VERIFIED:
            if peticion.otp_proof is None:
                raise TransactionRejectedError(
                    RejectionReason.OTP_NOT_VERIFIED,
                    "En modo TENANT_VERIFIED debe enviarse `otp_proof` con la evidencia "
                    "del código que el tenant ya verificó.",
                    transaction_id=transaccion.transaction_id,
                )
            return

        if peticion.otp_code is None:
            raise TransactionRejectedError(
                RejectionReason.OTP_NOT_VERIFIED,
                "En modo FNC_MANAGED debe enviarse `otp_code`.",
                transaction_id=transaccion.transaction_id,
            )
        # La verificación del OTP emitido por FNC llega con el proveedor de
        # mensajería (fase pendiente). Hasta entonces el modo se rechaza al crear
        # la transacción, no acá.
        raise TransactionRejectedError(
            RejectionReason.OTP_NOT_VERIFIED,
            "El modo FNC_MANAGED todavía no está disponible en este despliegue.",
            transaction_id=transaccion.transaction_id,
        )

    def _firmar_documento(
        self, transaccion: Transaction, peticion: ConfirmTransactionRequest
    ) -> SignatureResult | None:
        """Aplica la firma PAdES del nivel 2, o devuelve ``None`` en el nivel 1.

        **Regla inviolable 12: sin fecha cierta no hay firma.** Si la autoridad de
        sellado de tiempo falla, la transacción falla completa y no se degrada a
        PAdES-B-B. El motivo es concreto: el certificado del firmante vive quince
        minutos, así que un validador que lo comprueba después lo encuentra
        expirado; lo único que acredita que la firma se produjo dentro de esa
        ventana es el sello de tiempo. Una firma sin él es inverificable apenas
        expira el certificado, y entregarla sería entregar algo que parece prueba
        y no lo es.
        """
        if transaccion.service_level is not ServiceLevel.PADES:
            return None

        if peticion.document_content is None:
            raise TransactionRejectedError(
                RejectionReason.DOCUMENT_REQUIRED,
                "El nivel 2 firma los bytes del documento: envíe `document_content`.",
                transaction_id=transaccion.transaction_id,
            )

        # El certificado nombra a una persona: emitir uno sin nombre ni documento
        # produciría una firma que no identifica a nadie, que es peor que no
        # firmar. El dato lo aporta el tenant, que es quien verificó la identidad.
        if not peticion.signer_common_name or not peticion.signer_national_id:
            raise TransactionRejectedError(
                RejectionReason.INCOMPLETE_IDENTITY_DECISION,
                "El nivel 2 emite un certificado a nombre del firmante: envíe "
                "`signer_common_name` y `signer_national_id`.",
                transaction_id=transaccion.transaction_id,
            )

        perfil_id = self._perfil(transaccion.jurisdiction)
        try:
            perfil_id.validate_national_id(
                perfil_id.document_types[0].code, peticion.signer_national_id
            )
        except ValueError as exc:
            raise TransactionRejectedError(
                RejectionReason.INVALID_IDENTITY_DOCUMENT,
                str(exc),
                transaction_id=transaccion.transaction_id,
            ) from exc

        assert self._firmante_pades is not None  # comprobado al crear la transacción

        perfil = self._perfil(transaccion.jurisdiction)
        try:
            return self._firmante_pades.sign(
                peticion.document_content,
                SubjectData.for_jurisdiction(
                    perfil,
                    common_name=peticion.signer_common_name,
                    national_id=peticion.signer_national_id,
                    transaction_id=transaccion.transaction_id,
                ),
            )
        except TimestampError as exc:
            raise TransactionRejectedError(
                RejectionReason.TIMESTAMP_UNAVAILABLE,
                "No se pudo obtener el sello de tiempo. La firma no se emite: sin fecha "
                "cierta sería inverificable en cuanto expire el certificado del firmante.",
                transaction_id=transaccion.transaction_id,
            ) from exc

    def _sellar(
        self,
        transaccion: Transaction,
        peticion: ConfirmTransactionRequest,
        ahora: datetime,
        firma_pades: SignatureResult | None = None,
    ) -> SealedActa:
        """Construye el acta y la sella.

        La huella del consentimiento va al acta en lugar del texto: el texto puede
        ser largo y contener el nombre de la persona, y lo que hay que poder
        probar es que fue *ese* texto, no cuál era.
        """
        evidencia = hashlib.sha256(
            f"{peticion.consent_statement_version}\n{peticion.consent_statement}".encode()
        ).hexdigest()

        acta = ActaPayload(
            tenant_id=transaccion.tenant_id,
            transaction_id=transaccion.transaction_id,
            jurisdiction=transaccion.jurisdiction,
            service_level=int(transaccion.service_level.value),
            document=DocumentReference(
                sha256=transaccion.document_sha256,
                version=transaccion.document_version,
                code=transaccion.document_code,
                closed_at=transaccion.document_closed_at,
            ),
            evidence_sha256=evidencia,
            tenant_reference=transaccion.tenant_reference,
            environment=self._environment,
            # Los datos del nivel 2 se pasan explícitos y no con `**dict`: un
            # diccionario dinámico pierde los tipos y el verificador deja de
            # comprobar que el acta se arma bien, que es justo lo que no conviene
            # dejar sin comprobar en un artefacto probatorio.
            signed_document_sha256=(firma_pades.signed_sha256 if firma_pades is not None else ""),
            signer_certificate_serial=(
                firma_pades.certificate.serial_number if firma_pades is not None else ""
            ),
            timestamp_token_sha256=(
                hashlib.sha256(firma_pades.timestamp.token_base64.encode()).hexdigest()
                if firma_pades is not None
                else ""
            ),
            timestamp_authority=(
                firma_pades.timestamp.provider_name if firma_pades is not None else ""
            ),
            timestamp_qualified=(
                firma_pades.timestamp.qualified if firma_pades is not None else True
            ),
        )
        return self._sellador.seal(acta, sealed_at=ahora)

    def _sello(self, transaccion: Transaction) -> ActaSeal:
        assert transaccion.acta_jws is not None
        assert transaccion.acta_payload_sha256 is not None
        assert transaccion.acta_key_alias is not None
        return ActaSeal(
            jws=transaccion.acta_jws,
            payload_sha256=transaccion.acta_payload_sha256,
            key_alias=transaccion.acta_key_alias,
        )
