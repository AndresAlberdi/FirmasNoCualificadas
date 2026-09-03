import { useCallback, useState } from 'react'
import { AlertTriangle, BadgeCheck, FileSearch, ShieldAlert, ShieldCheck } from 'lucide-react'
import {
  esArtefactoDePrueba,
  tieneFechaCierta,
  verificarActa,
  type ClavePublicaJwk,
  type ResultadoVerificacion,
} from '../lib/acta'

/**
 * Verificación pública del acta sellada.
 *
 * Este panel no consulta nuestra API para dar el veredicto: descarga las claves
 * públicas y comprueba la firma **en el navegador**. Es una diferencia de fondo,
 * no de implementación. Si el veredicto lo emitiera el servidor, el tercero
 * estaría confiando en nuestra palabra sobre nuestra propia acta; comprobándolo
 * acá, confía en la criptografía y en la clave publicada.
 *
 * De ahí que la interfaz muestre siempre de dónde salieron las claves: una
 * verificación contra claves de origen desconocido no prueba nada.
 */

/** Dónde publica el prestador sus claves de sello (ADR-0006). */
const URL_CLAVES_POR_DEFECTO = '/.well-known/fnc-keys.json'

interface Props {
  readonly onAuditar?: (detalle: string) => void
}

type EstadoClaves =
  | { readonly fase: 'sin-cargar' }
  | { readonly fase: 'cargando' }
  | { readonly fase: 'cargadas'; readonly claves: readonly ClavePublicaJwk[]; readonly origen: string }
  | { readonly fase: 'error'; readonly mensaje: string }

export default function VerificacionPublica({ onAuditar }: Props) {
  const [urlClaves, setUrlClaves] = useState(URL_CLAVES_POR_DEFECTO)
  const [claves, setClaves] = useState<EstadoClaves>({ fase: 'sin-cargar' })
  const [jws, setJws] = useState('')
  const [resultado, setResultado] = useState<ResultadoVerificacion | null>(null)

  const cargarClaves = useCallback(async () => {
    setClaves({ fase: 'cargando' })
    try {
      const respuesta = await fetch(urlClaves)
      if (!respuesta.ok) {
        setClaves({ fase: 'error', mensaje: `El servidor respondió ${respuesta.status}.` })
        return
      }
      const cuerpo = (await respuesta.json()) as { keys?: ClavePublicaJwk[] }
      if (!Array.isArray(cuerpo.keys) || cuerpo.keys.length === 0) {
        setClaves({ fase: 'error', mensaje: 'El documento no contiene un conjunto de claves.' })
        return
      }
      setClaves({ fase: 'cargadas', claves: cuerpo.keys, origen: urlClaves })
    } catch (error) {
      setClaves({
        fase: 'error',
        mensaje: error instanceof Error ? error.message : 'No se pudo obtener el documento.',
      })
    }
  }, [urlClaves])

  const verificar = useCallback(async () => {
    if (claves.fase !== 'cargadas') return
    const veredicto = await verificarActa(jws.trim(), claves.claves)
    setResultado(veredicto)
    onAuditar?.(
      veredicto.valido
        ? `Acta verificada con la clave ${veredicto.kid}`
        : `Acta rechazada: ${veredicto.motivo}`,
    )
  }, [claves, jws, onAuditar])

  return (
    <section className="tarjeta space-y-4">
      <div>
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-100">
          <FileSearch className="h-4 w-4 text-institucional-500" aria-hidden />
          Verificación pública del acta
        </h2>
        <p className="mt-1 text-xs leading-relaxed text-slate-500">
          La comprobación se hace en este navegador con WebCrypto, sin consultar nuestra API. Un
          tercero puede repetirla con las mismas claves públicas y sin nuestra intervención.
        </p>
      </div>

      <div className="space-y-2">
        <label className="etiqueta block" htmlFor="url-claves">
          Origen de las claves públicas
        </label>
        <div className="flex flex-wrap gap-2">
          <input
            id="url-claves"
            className="min-w-0 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200"
            value={urlClaves}
            onChange={(evento) => setUrlClaves(evento.target.value)}
          />
          <button
            type="button"
            className="rounded-md bg-institucional-600 px-3 py-2 text-xs font-medium text-white hover:bg-institucional-500"
            onClick={() => void cargarClaves()}
          >
            Cargar claves
          </button>
        </div>
        <EstadoDeClaves estado={claves} />
      </div>

      <div className="space-y-2">
        <label className="etiqueta block" htmlFor="acta-jws">
          Acta sellada (JWS compacto)
        </label>
        <textarea
          id="acta-jws"
          rows={4}
          spellCheck={false}
          placeholder="eyJhbGciOiJFUzI1NiIsInR5cCI6IkpPU0UiLCJraWQiOiJ..."
          className="w-full resize-y rounded-md border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-200"
          value={jws}
          onChange={(evento) => {
            setJws(evento.target.value)
            // Un veredicto viejo junto a un acta nueva es peor que no mostrar nada.
            setResultado(null)
          }}
        />
        <button
          type="button"
          disabled={claves.fase !== 'cargadas' || jws.trim() === ''}
          className="rounded-md bg-institucional-600 px-4 py-2 text-xs font-medium text-white hover:bg-institucional-500 disabled:cursor-not-allowed disabled:bg-slate-800 disabled:text-slate-500"
          onClick={() => void verificar()}
        >
          Verificar acta
        </button>
      </div>

      {resultado ? <Veredicto resultado={resultado} /> : null}
    </section>
  )
}

function EstadoDeClaves({ estado }: { readonly estado: EstadoClaves }) {
  switch (estado.fase) {
    case 'sin-cargar':
      return (
        <p className="text-xs text-slate-500">
          Todavía no hay claves cargadas: sin ellas no hay nada contra qué comprobar.
        </p>
      )
    case 'cargando':
      return <p className="text-xs text-slate-500">Descargando el conjunto de claves…</p>
    case 'error':
      return (
        <p className="flex items-start gap-1.5 text-xs text-amber-300">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          No se pudieron cargar las claves: {estado.mensaje}
        </p>
      )
    case 'cargadas':
      return (
        <div className="text-xs text-slate-400">
          <p>
            {estado.claves.length} clave(s) desde <span className="font-mono">{estado.origen}</span>
          </p>
          <ul className="mt-1 space-y-0.5">
            {estado.claves.map((clave) => (
              <li key={clave.kid} className="dato">
                {clave.kid}
              </li>
            ))}
          </ul>
        </div>
      )
  }
}

function Veredicto({ resultado }: { readonly resultado: ResultadoVerificacion }) {
  if (!resultado.valido) {
    return (
      <div
        role="status"
        className="rounded-lg border border-rose-500/30 bg-rose-500/5 p-4 text-xs text-rose-200"
      >
        <p className="flex items-center gap-2 text-sm font-semibold text-rose-300">
          <ShieldAlert className="h-4 w-4" aria-hidden />
          Acta no válida · {resultado.motivo}
        </p>
        <p className="mt-1.5 leading-relaxed">{resultado.detalle}</p>
      </div>
    )
  }

  const { contenido } = resultado
  const dePrueba = esArtefactoDePrueba(contenido)

  return (
    <div
      role="status"
      className="space-y-3 rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4 text-xs"
    >
      <p className="flex items-center gap-2 text-sm font-semibold text-emerald-300">
        <ShieldCheck className="h-4 w-4" aria-hidden />
        Acta auténtica e íntegra
      </p>
      <p className="leading-relaxed text-slate-300">
        El contenido no se alteró desde que se selló, y lo selló quien posee la clave privada de{' '}
        <span className="font-mono">{resultado.kid}</span>. Esto no acredita los hechos que el acta
        afirma: la verificación de identidad la declara el cliente bajo su responsabilidad
        (ADR-0009).
      </p>

      {dePrueba ? (
        <p className="flex items-start gap-1.5 rounded-md bg-amber-500/10 px-3 py-2 text-amber-200">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          Artefacto de un entorno de pruebas
          {contenido.environment ? ` (${contenido.environment})` : ''}. No debe presentarse como
          prueba de un acto de firma.
        </p>
      ) : null}

      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        <Campo titulo="Transacción" valor={contenido.transaction_id} />
        <Campo titulo="Cliente" valor={contenido.tenant_id} />
        <Campo titulo="Jurisdicción" valor={contenido.jurisdiction} />
        <Campo titulo="Nivel de servicio" valor={String(contenido.service_level)} />
        <Campo titulo="Documento (SHA-256)" valor={contenido.document.sha256} />
        <Campo titulo="Versión del documento" valor={String(contenido.document.version)} />
        <Campo titulo="Evidencia (SHA-256)" valor={contenido.evidence_sha256} />
        <Campo titulo="Sellada el" valor={contenido.sealed_at} />
        {contenido.tenant_reference ? (
          <Campo titulo="Referencia del cliente" valor={contenido.tenant_reference} />
        ) : null}
        {contenido.signed_document_sha256 ? (
          <Campo titulo="Documento firmado (SHA-256)" valor={contenido.signed_document_sha256} />
        ) : null}
      </dl>

      <SelloDeTiempo contenido={contenido} />
    </div>
  )
}

function SelloDeTiempo({
  contenido,
}: {
  readonly contenido: Extract<ResultadoVerificacion, { valido: true }>['contenido']
}) {
  const sello = contenido.timestamp
  if (!sello) {
    return (
      <p className="text-slate-400">
        Sin sello de tiempo de una autoridad externa: la fecha que consta es la del sellado por el
        prestador, no una fecha cierta oponible frente a terceros.
      </p>
    )
  }

  if (!tieneFechaCierta(contenido)) {
    return (
      <p className="flex items-start gap-1.5 rounded-md bg-amber-500/10 px-3 py-2 text-amber-200">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        Sello emitido por «{sello.authority}», que no es una autoridad de sellado cualificada.
        Acredita que el mecanismo funcionó, no la fecha del acto.
      </p>
    )
  }

  return (
    <p className="flex items-start gap-1.5 text-emerald-200">
      <BadgeCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      Fecha cierta acreditada por «{sello.authority}» (autoridad de sellado cualificada).
    </p>
  )
}

function Campo({ titulo, valor }: { readonly titulo: string; readonly valor: string }) {
  return (
    <div>
      <dt className="etiqueta">{titulo}</dt>
      <dd className="dato">{valor}</dd>
    </div>
  )
}
