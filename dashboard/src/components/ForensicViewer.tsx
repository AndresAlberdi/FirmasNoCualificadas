import { useCallback, useMemo, useState } from 'react'
import {
  AlertTriangle,
  Clock,
  Download,
  Eye,
  EyeOff,
  Fingerprint,
  Globe,
  KeyRound,
  Loader2,
  MessageSquareLock,
  ShieldCheck,
} from 'lucide-react'
import type { AccionAuditada, Transaccion } from '../lib/types'
import {
  abreviarHash,
  colorPuntajeBiometrico,
  enmascararCedula,
  enmascararTelefono,
  formatearCedula,
  formatearFechaPy,
  porcentaje,
} from '../lib/format'

type Pestania = 'biometria' | 'red' | 'consentimiento' | 'criptografia'

interface Props {
  transaccion: Transaccion
  /** Se invoca en cada acción sensible; el backend la persiste en el log de auditoría del panel. */
  onAuditar: (accion: AccionAuditada, detalle?: string) => void
}

const PESTANIAS: { id: Pestania; etiqueta: string; icono: typeof Fingerprint }[] = [
  { id: 'biometria', etiqueta: 'Biometría', icono: Fingerprint },
  { id: 'red', etiqueta: 'Red', icono: Globe },
  { id: 'consentimiento', etiqueta: 'Consentimiento', icono: MessageSquareLock },
  { id: 'criptografia', etiqueta: 'Criptografía y TSA', icono: KeyRound },
]

function Campo({ etiqueta, children }: { etiqueta: string; children: React.ReactNode }) {
  return (
    <div className="border-b border-slate-800/70 py-2 last:border-0">
      <div className="etiqueta">{etiqueta}</div>
      <div className="mt-1 text-sm text-slate-200">{children}</div>
    </div>
  )
}

export default function ForensicViewer({ transaccion, onAuditar }: Props) {
  const [pestania, setPestania] = useState<Pestania>('biometria')
  const [piiRevelado, setPiiRevelado] = useState(false)
  const [descargando, setDescargando] = useState<'firmado' | 'evidencias' | null>(null)

  const { identity, network, consent, crypto } = transaccion

  const revelarPii = useCallback(() => {
    const siguiente = !piiRevelado
    setPiiRevelado(siguiente)
    if (siguiente) {
      // Toda revelación de datos personales queda registrada de forma inmutable.
      onAuditar('REVEAL_PII', `Cédula y capturas de la transacción ${transaccion.transactionId}`)
    }
  }, [piiRevelado, onAuditar, transaccion.transactionId])

  const descargar = useCallback(
    async (tipo: 'firmado' | 'evidencias') => {
      setDescargando(tipo)
      onAuditar(tipo === 'firmado' ? 'DOWNLOAD_SIGNED_PDF' : 'DOWNLOAD_EVIDENCE_PDF')
      // En el prototipo se simula la latencia de generación de la URL pre-firmada
      // de S3, cuya vigencia real es de 300 segundos.
      await new Promise((resolver) => setTimeout(resolver, 900))
      setDescargando(null)
    },
    [onAuditar],
  )

  const cedulaVisible = useMemo(
    () => (piiRevelado ? formatearCedula(identity.nationalId) : enmascararCedula(identity.nationalId)),
    [piiRevelado, identity.nationalId],
  )

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[320px_1fr]">
      {/* ------------------------------------------------ Columna de metadatos */}
      <aside className="space-y-4">
        <div className="tarjeta">
          <div className="etiqueta">Transacción</div>
          <div className="valor-mono mt-1">{transaccion.transactionId}</div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-400 ring-1 ring-emerald-500/30">
              {transaccion.status}
            </span>
            <span className="rounded-full bg-institucional-500/10 px-3 py-1 text-xs font-medium text-institucional-500 ring-1 ring-institucional-500/30">
              {crypto.signatureFormat}
            </span>
          </div>

          <div className="mt-4 space-y-1">
            <Campo etiqueta="Cliente B2B">{transaccion.b2bClientName}</Campo>
            <Campo etiqueta="Documento">{transaccion.documentFilename}</Campo>
            <Campo etiqueta="Inicio">{formatearFechaPy(transaccion.createdAt)}</Campo>
            <Campo etiqueta="Finalización">{formatearFechaPy(transaccion.completedAt)}</Campo>
          </div>
        </div>

        <div
          className={`tarjeta flex items-start gap-3 ${
            transaccion.integrityVerified
              ? 'border-emerald-500/30 bg-emerald-500/5'
              : 'border-rose-500/40 bg-rose-500/10'
          }`}
        >
          {transaccion.integrityVerified ? (
            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" aria-hidden />
          ) : (
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-rose-400" aria-hidden />
          )}
          <div>
            <p className="text-sm font-medium text-slate-100">
              {transaccion.integrityVerified
                ? 'Integridad verificada'
                : 'Discrepancia de integridad'}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              {transaccion.integrityVerified
                ? 'El hash almacenado coincide con el documento resguardado en la bóveda.'
                : 'El hash del documento no coincide con el registrado. Incidente notificado a SecOps.'}
            </p>
          </div>
        </div>

        <div className="tarjeta space-y-2">
          <button
            type="button"
            onClick={() => void descargar('firmado')}
            disabled={descargando !== null}
            className="flex w-full items-center justify-center gap-2 rounded-lg bg-institucional-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-institucional-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {descargando === 'firmado' ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="h-4 w-4" aria-hidden />
            )}
            Descargar PDF firmado
          </button>

          <button
            type="button"
            onClick={() => void descargar('evidencias')}
            disabled={descargando !== null}
            className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-700 px-4 py-2.5 text-sm font-medium text-slate-200 transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {descargando === 'evidencias' ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <Download className="h-4 w-4" aria-hidden />
            )}
            Descargar expediente
          </button>

          <p className="pt-1 text-[11px] leading-relaxed text-slate-500">
            Las descargas usan URLs pre-firmadas con vigencia de 300 segundos y quedan
            registradas en el log de auditoría del panel.
          </p>
        </div>
      </aside>

      {/* ------------------------------------------------- Panel de evidencias */}
      <section className="tarjeta">
        <div
          role="tablist"
          aria-label="Evidencias forenses"
          className="flex flex-wrap gap-1 border-b border-slate-800 pb-3"
        >
          {PESTANIAS.map(({ id, etiqueta, icono: Icono }) => (
            <button
              key={id}
              role="tab"
              type="button"
              aria-selected={pestania === id}
              onClick={() => setPestania(id)}
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition ${
                pestania === id
                  ? 'bg-institucional-600/15 font-medium text-institucional-500'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
              }`}
            >
              <Icono className="h-4 w-4" aria-hidden />
              {etiqueta}
            </button>
          ))}
        </div>

        <div className="pt-5">
          {pestania === 'biometria' && (
            <div className="space-y-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <h3 className="text-sm font-semibold text-slate-100">
                    Verificación biométrica uno a uno
                  </h3>
                  <p className="mt-1 text-xs text-slate-400">
                    Comparación entre la fotografía del documento y la captura en vivo.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={revelarPii}
                  className="flex shrink-0 items-center gap-2 rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 transition hover:bg-slate-800"
                >
                  {piiRevelado ? (
                    <EyeOff className="h-4 w-4" aria-hidden />
                  ) : (
                    <Eye className="h-4 w-4" aria-hidden />
                  )}
                  {piiRevelado ? 'Ocultar datos personales' : 'Revelar datos personales'}
                </button>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {['Fotografía del documento', 'Captura en vivo (liveness)'].map((titulo) => (
                  <figure key={titulo} className="overflow-hidden rounded-lg border border-slate-800">
                    <div
                      className={`flex h-40 items-center justify-center bg-gradient-to-br from-slate-800 to-slate-900 text-xs text-slate-500 transition ${
                        piiRevelado ? '' : 'blur-md'
                      }`}
                    >
                      {piiRevelado ? 'Imagen disponible en el expediente' : 'Contenido protegido'}
                    </div>
                    <figcaption className="border-t border-slate-800 px-3 py-2 text-[11px] text-slate-400">
                      {titulo}
                    </figcaption>
                  </figure>
                ))}
              </div>

              <div className="flex flex-wrap items-center gap-4 rounded-lg bg-slate-800/40 p-4">
                <div>
                  <div className="etiqueta">Coincidencia facial</div>
                  <div
                    className={`text-2xl font-semibold ${colorPuntajeBiometrico(identity.facialMatchScore)}`}
                  >
                    {porcentaje(identity.facialMatchScore)}
                  </div>
                </div>
                <div className="h-10 w-px bg-slate-700" aria-hidden />
                <div>
                  <div className="etiqueta">Prueba de vida</div>
                  <div className="text-sm text-emerald-400">
                    {identity.livenessDetected ? 'Aprobada' : 'No acreditada'}
                  </div>
                </div>
                <div className="h-10 w-px bg-slate-700" aria-hidden />
                <div>
                  <div className="etiqueta">AML / PEP</div>
                  <div className="text-sm text-slate-200">{identity.amlPepResult}</div>
                </div>
              </div>

              <div>
                <Campo etiqueta="Nombre completo">
                  {identity.firstName} {identity.lastName}
                </Campo>
                <Campo etiqueta="Cédula de identidad">
                  <span className="font-mono">{cedulaVisible}</span>
                </Campo>
                <Campo etiqueta="Fecha de nacimiento">{identity.birthDate}</Campo>
                <Campo etiqueta="Confianza del OCR">{porcentaje(identity.ocrConfidence)}</Campo>
                <Campo etiqueta="MRZ leída">
                  <span className="valor-mono">
                    {piiRevelado ? identity.ocrMrzRaw : '•'.repeat(44)}
                  </span>
                </Campo>
                <Campo etiqueta="Proveedor de verificación">
                  {identity.verificationPartnerId}
                </Campo>
              </div>
            </div>
          )}

          {pestania === 'red' && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-slate-100">
                Origen técnico de la conexión
              </h3>
              <Campo etiqueta="Dirección IP pública">
                <span className="font-mono">{network.clientIp}</span>
              </Campo>
              <Campo etiqueta="Puerto de origen">{network.sourcePort}</Campo>
              <Campo etiqueta="Proveedor de acceso">{network.geolocation?.isp ?? '—'}</Campo>
              <Campo etiqueta="Ubicación estimada">
                {network.geolocation
                  ? `${network.geolocation.city}, ${network.geolocation.countryCode} · ${network.geolocation.latitude}, ${network.geolocation.longitude}`
                  : '—'}
              </Campo>
              <Campo etiqueta="Agente de usuario">
                <span className="valor-mono">{network.userAgent}</span>
              </Campo>
              <Campo etiqueta="Canal seguro">
                {network.tlsVersion} · {network.tlsCipher}
              </Campo>
              <p className="rounded-lg bg-amber-500/5 p-3 text-xs text-amber-300/80 ring-1 ring-amber-500/20">
                La geolocalización por dirección IP es orientativa y no acredita por sí sola la
                ubicación física del firmante.
              </p>
            </div>
          )}

          {pestania === 'consentimiento' && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-slate-100">
                Acto de voluntad y control exclusivo de los medios
              </h3>

              <blockquote className="rounded-lg border-l-2 border-institucional-600 bg-slate-800/40 p-4 text-sm italic text-slate-300">
                {consent.consentStatement}
              </blockquote>
              <Campo etiqueta="Hash SHA-256 de la declaración">
                <span className="valor-mono">{consent.consentStatementSha256}</span>
              </Campo>

              {consent.otpChannels.map((canal) => (
                <div key={canal.providerMessageId} className="rounded-lg border border-slate-800 p-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
                    <MessageSquareLock className="h-4 w-4 text-institucional-500" aria-hidden />
                    {canal.channelType}
                    <span className="font-mono text-xs text-slate-400">
                      {piiRevelado ? canal.destination : enmascararTelefono(canal.destination)}
                    </span>
                  </div>

                  <ol className="mt-3 space-y-2 border-l border-slate-800 pl-4 text-xs text-slate-400">
                    <li className="flex items-start gap-2">
                      <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                      Código enviado · {formatearFechaPy(canal.otpSentTimestamp)}
                    </li>
                    <li className="flex items-start gap-2">
                      <Clock className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
                      Código verificado · {formatearFechaPy(canal.otpVerifiedTimestamp)}
                    </li>
                  </ol>

                  <div className="mt-3">
                    <Campo etiqueta="Identificador del proveedor de mensajería">
                      <span className="valor-mono">{canal.providerMessageId}</span>
                    </Campo>
                    <Campo etiqueta="Hash SHA-256 del código (nunca se almacena en claro)">
                      <span className="valor-mono">{canal.otpCodeHash}</span>
                    </Campo>
                  </div>
                </div>
              ))}
            </div>
          )}

          {pestania === 'criptografia' && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-slate-100">
                Integridad del documento y fecha cierta
              </h3>

              <Campo etiqueta="Hash SHA-256 del PDF original">
                <span className="valor-mono" title={crypto.originalPdfSha256}>
                  {abreviarHash(crypto.originalPdfSha256, 20)}
                </span>
              </Campo>
              <Campo etiqueta="Hash SHA-256 del PDF firmado">
                <span className="valor-mono" title={crypto.signedPdfSha256}>
                  {abreviarHash(crypto.signedPdfSha256, 20)}
                </span>
              </Campo>

              <div className="rounded-lg border border-slate-800 p-4">
                <div className="etiqueta mb-2">Certificado del firmante (un solo uso)</div>
                <Campo etiqueta="Sujeto">
                  CN = {identity.firstName} {identity.lastName} · serialNumber = PY-
                  {piiRevelado ? identity.nationalId : '*'.repeat(identity.nationalId.length)}
                </Campo>
                <Campo etiqueta="Número de serie">
                  <span className="valor-mono">{crypto.userCertificateSerial}</span>
                </Campo>
                <Campo etiqueta="Emisor">
                  CA Intermedia del PSCNC · serie {crypto.caIntermediateSerial}
                </Campo>
                <Campo etiqueta="Algoritmo">{crypto.signatureAlgorithm}</Campo>
                <Campo etiqueta="Uso de clave">digitalSignature · nonRepudiation</Campo>
              </div>

              <div className="rounded-lg border border-emerald-500/25 bg-emerald-500/5 p-4">
                <div className="etiqueta mb-2 text-emerald-400">
                  Sello de tiempo cualificado (RFC 3161)
                </div>
                <Campo etiqueta="Autoridad de sellado">{crypto.tsaProviderName}</Campo>
                <Campo etiqueta="Número de serie del token">
                  <span className="valor-mono">{crypto.tsaSerialNumber}</span>
                </Campo>
                <Campo etiqueta="Hora oficial">{formatearFechaPy(crypto.timestampUtc)}</Campo>
              </div>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}
