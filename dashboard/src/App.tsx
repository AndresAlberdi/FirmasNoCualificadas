import { useCallback, useState } from 'react'
import { Lock, ScrollText, ShieldCheck } from 'lucide-react'
import ForensicViewer from './components/ForensicViewer'
import { transaccionDemo } from './lib/mockData'
import type { AccionAuditada, EventoAuditoriaPanel } from './lib/types'

/**
 * Prototipo del Folleto Forense. La transacción proviene de datos sintéticos;
 * al integrar con la API se reemplaza por `GET /v1/signing-sessions/{id}/evidence`.
 */
export default function App() {
  const [eventos, setEventos] = useState<EventoAuditoriaPanel[]>([
    {
      action: 'VIEW_TRANSACTION',
      transactionId: transaccionDemo.transactionId,
      at: new Date().toISOString(),
    },
  ])

  const auditar = useCallback((accion: AccionAuditada, detalle?: string) => {
    // En producción esta llamada viaja al backend y se persiste de forma inmutable
    // en `PSCNC_Dashboard_Audit_Log` con el identificador del usuario del panel.
    setEventos((previos) => [
      {
        action: accion,
        transactionId: transaccionDemo.transactionId,
        at: new Date().toISOString(),
        detail: detalle,
      },
      ...previos,
    ])
  }, [])

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/70 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 place-items-center rounded-lg bg-institucional-600">
              <ShieldCheck className="h-5 w-5 text-white" aria-hidden />
            </div>
            <div>
              <h1 className="text-sm font-semibold text-slate-100">
                Folleto Forense · Portal de Evidencias B2B
              </h1>
              <p className="text-xs text-slate-500">
                Prestador de Servicios de Confianza No Cualificado — Paraguay
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-emerald-400 ring-1 ring-emerald-500/30">
              <Lock className="h-3.5 w-3.5" aria-hidden />
              mTLS activo
            </span>
            <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-300 ring-1 ring-slate-700">
              MFA verificado
            </span>
            <span className="rounded-full bg-slate-800 px-3 py-1 text-slate-300 ring-1 ring-slate-700">
              B2B_Legal_Auditor
            </span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl space-y-5 px-5 py-6">
        <div className="rounded-lg border border-amber-500/25 bg-amber-500/5 px-4 py-3 text-xs text-amber-200/90">
          Prototipo con datos sintéticos. No contiene información de personas reales.
        </div>

        <ForensicViewer transaccion={transaccionDemo} onAuditar={auditar} />

        <section className="tarjeta">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
            <ScrollText className="h-4 w-4 text-institucional-500" aria-hidden />
            Registro de auditoría del panel
          </h2>
          <p className="mt-1 text-xs text-slate-500">
            Toda consulta, revelación de datos personales y descarga queda registrada de forma
            inmutable con retención de dos años.
          </p>

          <ul className="mt-4 divide-y divide-slate-800 text-xs">
            {eventos.map((evento, indice) => (
              <li key={`${evento.at}-${indice}`} className="flex flex-wrap gap-2 py-2">
                <span className="font-mono text-slate-500">
                  {new Date(evento.at).toISOString()}
                </span>
                <span className="font-medium text-slate-200">{evento.action}</span>
                {evento.detail ? <span className="text-slate-400">· {evento.detail}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="mx-auto max-w-7xl px-5 pb-8 text-[11px] leading-relaxed text-slate-600">
        La firma documentada es una firma electrónica no cualificada: tiene validez jurídica por
        el principio de no discriminación (Art. 39 de la Ley N.º 6822/2021), sin la presunción
        legal de autoría propia de la firma cualificada.
      </footer>
    </div>
  )
}
