/**
 * Datos sintéticos del prototipo. Al integrar con la API real, este módulo se
 * reemplaza por un cliente de `GET /v1/signing-sessions/{id}/evidence`.
 *
 * Prohibido incorporar aquí datos de personas reales.
 */

import type { Transaccion } from './types'

export const transaccionDemo: Transaccion = {
  transactionId: '9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d',
  b2bClientId: 'aseguradora-py',
  b2bClientName: 'Aseguradora del Paraguay S.A.',
  status: 'SIGNING_COMPLETED',
  createdAt: '2026-08-22T21:43:23Z',
  completedAt: '2026-08-22T21:43:35Z',
  documentFilename: 'poliza-vida-2026-004821.pdf',
  integrityVerified: true,
  identity: {
    documentType: 'CI_PY',
    nationalId: '4829153',
    firstName: 'Firmante',
    lastName: 'De Prueba',
    birthDate: '1985-03-14',
    ocrMrzRaw: 'IDPRY4829153<<<<<<<<<<<<<<<<8503140M3001019PRY<<<<<<<<<<<8',
    ocrConfidence: 0.99,
    facialMatchScore: 0.985,
    livenessDetected: true,
    verificationPartnerId: 'onboarding-9f2c41',
    amlPepChecked: true,
    amlPepResult: 'SIN COINCIDENCIAS',
  },
  network: {
    clientIp: '190.104.128.5',
    sourcePort: 51234,
    userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 18_2 like Mac OS X) AppleWebKit/605.1.15',
    tlsVersion: 'TLSv1.3',
    tlsCipher: 'TLS_AES_256_GCM_SHA384',
    geolocation: {
      countryCode: 'PY',
      city: 'Asunción',
      latitude: -25.2637,
      longitude: -57.5759,
      isp: 'Telecel S.A. (Tigo)',
    },
  },
  consent: {
    consentStatement:
      'Declaro que reviso y acepto firmar electrónicamente el documento identificado, ' +
      'reconociendo que la firma electrónica no cualificada me vincula conforme a la ' +
      'Ley N.º 6822/2021 de la República del Paraguay.',
    consentStatementSha256: '7d793037a0760186574b0282f2f435e7f0a1c2b3d4e5f60718293a4b5c6d7e8f',
    otpChannels: [
      {
        channelType: 'WHATSAPP',
        destination: '+595981123456',
        otpSentTimestamp: '2026-08-22T21:42:58Z',
        otpVerifiedTimestamp: '2026-08-22T21:43:19Z',
        providerMessageId: 'wamid.HBgMNTk1OTgxMTIzNDU2FQIAERgSN0Y',
        otpCodeHash: '3f79bb7b435b05321651daefd374cdc681dc06faa65e374e38337b88ca046dea',
      },
    ],
  },
  crypto: {
    originalPdfSha256: 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    signedPdfSha256: 'a4f4944be6fc3a1599bf461c9e6fa91418be21e46422b934ca495991b782c918',
    userCertificateSerial: '5f2a1c9e4b7d3086',
    caIntermediateSerial: '00b41e2f7c9d5a3801',
    signatureFormat: 'PAdES-B-T',
    signatureAlgorithm: 'SHA256withRSA',
    tsaProviderName: 'PCSC cualificado (Paraguay)',
    tsaSerialNumber: '841295832',
    timestampUtc: '2026-08-22T21:43:35Z',
  },
}
