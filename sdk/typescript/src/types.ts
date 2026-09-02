/**
 * Tipos del contrato público v1 de FirmasNoCualificadas.
 *
 * Espejo de `api/openapi.yaml`. Se escriben a mano y no se generan porque el
 * generador produce nombres y uniones que ocultan justamente lo que un
 * integrador necesita entender: qué manda el tenant, qué no debe mandar nunca, y
 * qué significa cada motivo de rechazo.
 *
 * Tres reglas del contrato que estos tipos hacen cumplir en tiempo de
 * compilación:
 *
 * 1. La decisión de identidad la toma el tenant. El servicio la asienta.
 * 2. El OTP viaja como prueba, **nunca el código**.
 * 3. El documento se identifica por su huella: el contenido no se envía.
 */

/** Los dos niveles de servicio (ADR-0007). */
export type ServiceLevel = "1" | "2";

/** Quién emite y verifica el código de un solo uso. */
export type OtpMode = "TENANT_VERIFIED" | "FNC_MANAGED";

export type OtpChannel = "WHATSAPP" | "SMS" | "EMAIL";

export type TransactionStatus = "CREATED" | "CONFIRMED" | "REJECTED" | "EXPIRED";

/**
 * Motivos de rechazo. Son **valores estables del contrato**: agregar uno es
 * compatible, renombrarlo no. Un motivo desconocido debe tratarse como fallo
 * genérico y registrarse, nunca ignorarse en silencio.
 */
export type RejectionReason =
  | "UNAUTHENTICATED"
  | "INVALID_SIGNATURE"
  | "REQUEST_EXPIRED"
  | "TENANT_NOT_ENABLED"
  | "TRANSACTION_NOT_FOUND"
  | "TRANSACTION_OF_ANOTHER_TENANT"
  | "TRANSACTION_ALREADY_CONFIRMED"
  | "TRANSACTION_EXPIRED"
  | "INVALID_STATE"
  | "IDENTITY_NOT_APPROVED"
  | "INCOMPLETE_IDENTITY_DECISION"
  | "OTP_NOT_VERIFIED"
  | "OTP_NOT_FOR_TRANSACTION"
  | "OTP_INCORRECT_CODE"
  | "OTP_ATTEMPTS_EXHAUSTED"
  | "OTP_EXPIRED"
  | "OTP_ALREADY_USED"
  | "INVALID_DOCUMENT"
  | "DOCUMENT_TAMPERED"
  | "DOCUMENT_REQUIRED"
  | "DOCUMENT_TOO_LARGE"
  | "EXCLUDED_LEGAL_ACT"
  | "UNSUPPORTED_JURISDICTION"
  | "INVALID_IDENTITY_DOCUMENT"
  | "SERVICE_LEVEL_NOT_CONTRACTED"
  | "SERVICE_LEVEL_UNAVAILABLE"
  | "IDEMPOTENCY_CONFLICT"
  | "IDEMPOTENCY_KEY_REQUIRED"
  | "SEALING_FAILED"
  | "EVIDENCE_NOT_PERSISTED"
  | "TIMESTAMP_UNAVAILABLE"
  | "INTERNAL_ERROR";

/**
 * Decisión de identidad **ya tomada por el tenant**.
 *
 * El servicio no la revisa: la asienta como evidencia, registrando quién decidió
 * y con qué política. Dos controles de identidad sobre el mismo acto no se
 * suman — gana el más laxo.
 */
export interface IdentityDecision {
  readonly approved: boolean;
  /** Umbral aplicado, normalizado a 0-1. */
  readonly threshold_applied: number;
  /** Puntaje obtenido, **normalizado a 0-1**. */
  readonly score?: number;
  /**
   * Escala de la que viene el puntaje. Un `98` sin escala declarada es
   * indistinguible de un `0.98` mal convertido.
   */
  readonly score_scale?: "0-1" | "0-100";
  readonly model_version: string;
  readonly policy_version: string;
  readonly provider_reference: string;
  readonly liveness_verified?: boolean;
  readonly verified_at?: string;
}

/**
 * Evidencia de un OTP que el tenant ya verificó.
 *
 * Nótese que **no hay campo para el código**: no es un olvido, es el contrato.
 * Lo que se acredita es el acto, no el secreto que lo permitió.
 */
export interface OtpProof {
  readonly otp_reference: string;
  readonly channel: OtpChannel;
  /** Destino enmascarado. El servicio rechaza uno sin enmascarar. */
  readonly destination_masked: string;
  readonly sent_at: string;
  readonly verified_at: string;
}

/** El documento cerrado, identificado por su huella. */
export interface DocumentRef {
  readonly sha256: string;
  /** Sin la versión, una huella suelta no dice contra qué comparar. */
  readonly version: number;
  readonly code: string;
  readonly closed_at: string;
}

export interface CreateTransactionRequest {
  readonly tenant_reference: string;
  readonly document: DocumentRef;
  readonly identity_decision: IdentityDecision;
  readonly service_level?: ServiceLevel;
  readonly otp_mode?: OtpMode;
  readonly jurisdiction?: string;
  readonly metadata?: Readonly<Record<string, string>>;
}

export interface ConfirmTransactionRequest {
  readonly otp_proof?: OtpProof;
  /** Solo en `FNC_MANAGED`. Nunca se persiste ni se registra. */
  readonly otp_code?: string;
  readonly consent_statement: string;
  readonly consent_statement_version: string;
  readonly document_sha256: string;
  readonly signer_ip?: string;
  readonly signer_user_agent?: string;
}

export interface TransactionCreated {
  readonly transaction_id: string;
  readonly tenant_reference: string;
  readonly status: TransactionStatus;
  readonly service_level: ServiceLevel;
  readonly jurisdiction: string;
  readonly document_sha256: string;
  readonly created_at: string;
  readonly expires_at: string;
}

/** Lo que un tercero necesita para verify el acta por su cuenta. */
export interface ActaSeal {
  readonly jws: string;
  readonly payload_sha256: string;
  readonly key_alias: string;
  readonly algorithm: string;
  readonly jwks_url: string;
}

export interface TransactionConfirmed {
  readonly transaction_id: string;
  readonly tenant_reference: string;
  readonly status: TransactionStatus;
  readonly service_level: ServiceLevel;
  readonly confirmed_at: string;
  readonly acta: ActaSeal;
  readonly verification_code: string;
  readonly signed_document_sha256?: string;
  readonly timestamp_authority?: string;
}

export interface Artifacts {
  readonly transaction_id: string;
  readonly status: TransactionStatus;
  readonly service_level: ServiceLevel;
  readonly acta?: ActaSeal;
  readonly verification_code?: string;
  readonly signed_document_url?: string;
  readonly url_expires_in_seconds?: number;
}

/** Constancia pública. No lleva ningún dato personal. */
export interface PublicVerification {
  readonly verification_code: string;
  readonly exists: boolean;
  readonly status?: TransactionStatus;
  readonly document_sha256?: string;
  readonly document_code?: string;
  readonly signed_at?: string;
  readonly jurisdiction?: string;
  readonly legal_basis?: string;
  readonly service_level?: ServiceLevel;
  readonly acta_jws?: string;
}

export interface ErrorResponse {
  readonly motivo: RejectionReason;
  /** Para una persona. **Puede cambiar entre versiones**: no lo programe. */
  readonly mensaje: string;
  readonly transaction_id?: string;
  readonly detalle?: Readonly<Record<string, string | number | readonly string[]>>;
  readonly reintentable: boolean;
}

/**
 * Result de una llamada, en la forma que obliga a mirar el error.
 *
 * Se devuelve un resultado en lugar de lanzar porque un rechazo del contrato no
 * es excepcional: es una respuesta prevista que el tenant tiene que mapear a su
 * propia máquina de estados.
 */
export type Result<T> =
  | { readonly ok: true; readonly value: T }
  | { readonly ok: false; readonly error: ErrorResponse };
