/**
 * @vitest-environment jsdom
 *
 * Pruebas del panel de verificación pública.
 *
 * Lo que se comprueba acá no es la criptografía —eso lo cubre `acta.test.ts`—
 * sino que la interfaz **no afirme de más**: que no permita verificar sin claves,
 * que diga de dónde salieron, y que un acta de un entorno de pruebas se presente
 * como tal aunque su firma sea perfectamente válida.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import VerificacionPublica from '../src/components/VerificacionPublica'
import { FncPublicClient } from '../src/lib/api'
import type { ClavePublicaJwk } from '../src/lib/acta'

const KID = 'alias/fnc/prod/aseguradora-py/acta-seal/v1'

function aBase64Url(datos: Uint8Array | string): string {
  const bytes = typeof datos === 'string' ? new TextEncoder().encode(datos) : datos
  let binario = ''
  for (const b of bytes) binario += String.fromCharCode(b)
  return btoa(binario).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

let clave: CryptoKeyPair
let jwk: ClavePublicaJwk

async function sellar(contenido: Record<string, unknown>): Promise<string> {
  const cabecera = aBase64Url(JSON.stringify({ alg: 'ES256', typ: 'JOSE', kid: KID }))
  const cuerpo = aBase64Url(JSON.stringify(contenido))
  const firma = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    clave.privateKey,
    new TextEncoder().encode(`${cabecera}.${cuerpo}`),
  )
  return `${cabecera}.${cuerpo}.${aBase64Url(new Uint8Array(firma))}`
}

function acta(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    acta_version: 1,
    tenant_id: 'aseguradora-py',
    transaction_id: 'c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb',
    jurisdiction: 'PY',
    service_level: 1,
    document: { sha256: 'a'.repeat(64), version: 2, code: 'PROP-1', closed_at: '2026-09-02T14:30:00Z' },
    evidence_sha256: 'b'.repeat(64),
    sealed_at: '2026-09-02T14:31:15Z',
    ...extra,
  }
}

beforeEach(async () => {
  clave = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
    'sign',
    'verify',
  ])) as CryptoKeyPair
  const exportada = (await crypto.subtle.exportKey('jwk', clave.publicKey)) as {
    kty: string
    crv: string
    x: string
    y: string
  }
  jwk = { kty: exportada.kty, crv: exportada.crv, alg: 'ES256', use: 'sig', kid: KID, x: exportada.x, y: exportada.y }

  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify({ keys: [jwk] }), { status: 200 })),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

/** Carga las claves y pega un acta, que es el punto de partida de casi todo. */
async function prepararPanel(jws: string, onAuditar?: (detalle: string) => void) {
  const usuario = userEvent.setup()
  render(<VerificacionPublica onAuditar={onAuditar} />)
  await usuario.click(screen.getByRole('button', { name: /cargar claves/i }))
  // Coincidencia exacta: construir un `RegExp` a partir del `kid` obligaría a
  // escapar sus metacaracteres, y escaparlos a medias es peor que no usarlo.
  await screen.findByText(KID)
  await usuario.type(screen.getByLabelText(/acta sellada/i), jws)
  return usuario
}

describe('panel de verificación pública', () => {
  it('no deja verificar mientras no haya claves cargadas', () => {
    render(<VerificacionPublica />)

    // Sin claves no hay nada contra qué comprobar: ofrecer el botón sugeriría
    // que un veredicto es posible.
    expect(screen.getByRole('button', { name: /verificar acta/i })).toBeDisabled()
  })

  it('muestra el origen de las claves cargadas', async () => {
    const usuario = userEvent.setup()
    render(<VerificacionPublica />)

    await usuario.click(screen.getByRole('button', { name: /cargar claves/i }))

    // Una verificación contra claves de origen desconocido no prueba nada.
    expect(await screen.findByText(/\/\.well-known\/fnc-keys\.json/)).toBeInTheDocument()
  })

  it('informa cuando las claves no se pueden obtener', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 404 })))
    const usuario = userEvent.setup()
    render(<VerificacionPublica />)

    await usuario.click(screen.getByRole('button', { name: /cargar claves/i }))

    expect(await screen.findByText(/no se pudieron cargar las claves/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /verificar acta/i })).toBeDisabled()
  })

  it('declara auténtica un acta válida y aclara lo que no acredita', async () => {
    const usuario = await prepararPanel(await sellar(acta()))

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/acta auténtica e íntegra/i)).toBeInTheDocument()
    // El límite del veredicto: la identidad la declara el cliente.
    expect(screen.getByText(/no acredita los hechos que el acta afirma/i)).toBeInTheDocument()
  })

  it('rechaza un acta alterada y explica el motivo', async () => {
    const jws = await sellar(acta())
    const [cabecera, , firma] = jws.split('.')
    const otroCuerpo = aBase64Url(JSON.stringify(acta({ tenant_id: 'otro-tenant' })))
    const usuario = await prepararPanel(`${cabecera}.${otroCuerpo}.${firma}`)

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/FIRMA_INVALIDA/)).toBeInTheDocument()
    expect(screen.queryByText(/acta auténtica/i)).not.toBeInTheDocument()
  })

  it('marca como artefacto de prueba un acta de un entorno no productivo', async () => {
    // La firma es válida; lo que no es válido es presentarla como prueba.
    const usuario = await prepararPanel(
      await sellar(acta({ environment: 'dev', not_valid_for_production: true })),
    )

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/acta auténtica e íntegra/i)).toBeInTheDocument()
    expect(screen.getByText(/artefacto de un entorno de pruebas/i)).toBeInTheDocument()
  })

  it('distingue un sello de tiempo cualificado de uno que no lo es', async () => {
    const usuario = await prepararPanel(
      await sellar(
        acta({ timestamp: { token_sha256: 'c'.repeat(64), authority: 'TSA de Pruebas', qualified: false } }),
      ),
    )

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/no es una autoridad de sellado cualificada/i)).toBeInTheDocument()
    expect(screen.queryByText(/fecha cierta acreditada/i)).not.toBeInTheDocument()
  })

  it('reconoce la fecha cierta cuando la autoridad es cualificada', async () => {
    const usuario = await prepararPanel(
      await sellar(
        acta({ timestamp: { token_sha256: 'c'.repeat(64), authority: 'Confirma S.A.', qualified: true } }),
      ),
    )

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/fecha cierta acreditada/i)).toBeInTheDocument()
  })

  it('advierte que sin sello externo no hay fecha oponible a terceros', async () => {
    const usuario = await prepararPanel(await sellar(acta()))

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    expect(await screen.findByText(/no una fecha cierta oponible/i)).toBeInTheDocument()
  })

  it('registra en la auditoría tanto la aceptación como el rechazo', async () => {
    // Una consulta que no deja rastro no sirve para una pericia posterior.
    const auditar = vi.fn()
    const usuario = await prepararPanel(await sellar(acta()), auditar)

    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))
    await waitFor(() => expect(auditar).toHaveBeenCalledWith(expect.stringContaining(KID)))

    await usuario.clear(screen.getByLabelText(/acta sellada/i))
    await usuario.type(screen.getByLabelText(/acta sellada/i), 'no-es-un-acta')
    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))

    await waitFor(() =>
      expect(auditar).toHaveBeenCalledWith(expect.stringContaining('SOBRE_MAL_FORMADO')),
    )
  })

  it('retira el veredicto anterior al cambiar el acta', async () => {
    // Un veredicto viejo junto a un acta nueva se leería como veredicto de esta.
    const usuario = await prepararPanel(await sellar(acta()))
    await usuario.click(screen.getByRole('button', { name: /verificar acta/i }))
    await screen.findByText(/acta auténtica e íntegra/i)

    await usuario.type(screen.getByLabelText(/acta sellada/i), 'x')

    expect(screen.queryByText(/acta auténtica e íntegra/i)).not.toBeInTheDocument()
  })
})


describe('consulta por código contra la API', () => {
  /** Cliente con un `fetch` propio: no se toca la red en ninguna prueba. */
  function clienteQueResponde(constancia: unknown): FncPublicClient {
    return new FncPublicClient({
      fetchImpl: (async (entrada: RequestInfo | URL) => {
        const url = String(entrada)
        if (url.includes('fnc-keys.json')) {
          return new Response(JSON.stringify({ keys: [jwk] }), { status: 200 })
        }
        return new Response(JSON.stringify(constancia), { status: 200 })
      }) as typeof globalThis.fetch,
    })
  }

  it('trae la constancia, verifica su acta y muestra la norma aplicable', async () => {
    const jws = await sellar(acta())
    const usuario = userEvent.setup()
    render(
      <VerificacionPublica
        cliente={clienteQueResponde({
          verification_code: 'FNC-2026-000123',
          exists: true,
          status: 'SIGNING_COMPLETED',
          document_sha256: 'a'.repeat(64),
          jurisdiction: 'PY',
          legal_basis: 'Ley N.º 6822/2021',
          acta_jws: jws,
        })}
      />,
    )

    await usuario.type(screen.getByLabelText(/código de verificación/i), 'FNC-2026-000123')
    await usuario.click(screen.getByRole('button', { name: /consultar y verificar/i }))

    expect(await screen.findByText(/acta auténtica e íntegra/i)).toBeInTheDocument()
    expect(screen.getByText('Ley N.º 6822/2021')).toBeInTheDocument()
  })

  it('avisa cuando la constancia y el acta no describen el mismo acto', async () => {
    // Dos fuentes que se contradicen sobre el mismo acto: ninguna sirve como
    // prueba hasta saber cuál está mal.
    const jws = await sellar(acta())
    const usuario = userEvent.setup()
    render(
      <VerificacionPublica
        cliente={clienteQueResponde({
          verification_code: 'FNC-2026-000123',
          exists: true,
          document_sha256: 'f'.repeat(64), // no es el del acta
          jurisdiction: 'PY',
          acta_jws: jws,
        })}
      />,
    )

    await usuario.type(screen.getByLabelText(/código de verificación/i), 'FNC-2026-000123')
    await usuario.click(screen.getByRole('button', { name: /consultar y verificar/i }))

    expect(await screen.findByText(/no describen el mismo acto/i)).toBeInTheDocument()
  })

  it('un código inexistente no se presenta como un fallo del servicio', async () => {
    const usuario = userEvent.setup()
    render(
      <VerificacionPublica
        cliente={clienteQueResponde({ verification_code: 'FNC-X', exists: false })}
      />,
    )

    await usuario.type(screen.getByLabelText(/código de verificación/i), 'FNC-X')
    await usuario.click(screen.getByRole('button', { name: /consultar y verificar/i }))

    expect(await screen.findByText(/no corresponde a ninguna firma/i)).toBeInTheDocument()
    expect(screen.queryByText(/acta auténtica/i)).not.toBeInTheDocument()
  })
})
