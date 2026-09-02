/**
 * Contratos del panel, alineados con `pscnc.models.audit_trail` del backend.
 * Cualquier cambio aquí debe reflejarse en el modelo Pydantic y viceversa.
 */

export type EstadoFirma =
  | 'INITIALIZED'
  | 'ONBOARDING_COMPLETED'
  | 'SIGNING_COMPLETED'
  | 'FAILED'
  | 'REVOKED'
  | 'COMPROMISED'

export interface EvidenciaIdentidad {
  documentType: 'CI_PY' | 'PASAPORTE'
  nationalId: string
  firstName: string
  lastName: string
  birthDate: string
  ocrMrzRaw: string
  ocrConfidence: number
  facialMatchScore: number
  livenessDetected: boolean
  verificationPartnerId: string
  amlPepChecked: boolean
  amlPepResult: string
}

export interface EvidenciaRed {
  clientIp: string
  sourcePort: number
  userAgent: string
  tlsVersion: string
  tlsCipher: string
  geolocation?: {
    countryCode: string
    city: string
    latitude: number
    longitude: number
    isp: string
  }
}

export interface CanalOtp {
  channelType: 'WHATSAPP' | 'SMS' | 'EMAIL'
  destination: string
  otpSentTimestamp: string
  otpVerifiedTimestamp: string
  providerMessageId: string
  otpCodeHash: string
}

export interface EvidenciaConsentimiento {
  consentStatement: string
  consentStatementSha256: string
  otpChannels: CanalOtp[]
}

export interface EvidenciaCriptografica {
  originalPdfSha256: string
  signedPdfSha256: string
  userCertificateSerial: string
  caIntermediateSerial: string
  signatureFormat: string
  signatureAlgorithm: string
  tsaProviderName: string
  tsaSerialNumber: string
  timestampUtc: string
}

export interface Transaccion {
  transactionId: string
  b2bClientId: string
  b2bClientName: string
  status: EstadoFirma
  createdAt: string
  completedAt: string | null
  documentFilename: string
  identity: EvidenciaIdentidad
  network: EvidenciaRed
  consent: EvidenciaConsentimiento
  crypto: EvidenciaCriptografica
  /** Verdadero cuando el hash almacenado coincide con el recalculado sobre el objeto en S3. */
  integrityVerified: boolean
}

/** Acción registrada en `PSCNC_Dashboard_Audit_Log`. */
export type AccionAuditada =
  | 'VIEW_TRANSACTION'
  | 'REVEAL_PII'
  | 'DOWNLOAD_SIGNED_PDF'
  | 'DOWNLOAD_EVIDENCE_PDF'
  | 'VERIFY_ACTA'

export interface EventoAuditoriaPanel {
  action: AccionAuditada
  transactionId: string
  at: string
  detail?: string
}
