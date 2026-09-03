/**
 * Cliente de la API pública.
 *
 * Lo que estas pruebas fijan no es el transporte sino **la distinción entre
 * fallos**: «ese código no corresponde a ninguna firma» y «no pudimos preguntar»
 * son dos mensajes distintos para quien verifica, y confundirlos convierte una
 * caída del servicio en una acusación contra el documento.
 *
 * Todos los datos son sintéticos.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { FncPublicClient, constanciaCoincideConActa } from '../src/lib/api'
import type { ConstanciaPublica } from '../src/lib/api'
import type { ContenidoActa } from '../src/lib/acta'

afterEach(() => vi.restoreAllMocks())

function respuesta(cuerpo: unknown, status = 200): Response {
  return new Response(JSON.stringify(cuerpo), {
    status,
    headers: { 'content-type': 'application/json' },
  })
}

function clienteCon(fetchImpl: typeof globalThis.fetch): FncPublicClient {
  return new FncPublicClient({ fetchImpl })
}

const CONSTANCIA: ConstanciaPublica = {
  verification_code: 'FNC-2026-000123',
  exists: true,
  status: 'SIGNING_COMPLETED',
  document_sha256: 'a'.repeat(64),
  document_code: 'PROP-2026-000123',
  jurisdiction: 'PY',
  legal_basis: 'Ley N.º 6822/2021',
  service_level: 1,
  acta_jws: 'eyJ.eyJ.firma',
}

describe('constancia pública', () => {
  it('devuelve la constancia de un código existente', async () => {
    const cliente = clienteCon(vi.fn(async () => respuesta(CONSTANCIA)))

    const resultado = await cliente.constancia('FNC-2026-000123')

    expect(resultado.ok).toBe(true)
    if (!resultado.ok) return
    expect(resultado.datos.acta_jws).toBe('eyJ.eyJ.firma')
  })

  it('distingue un código inexistente de una caída del servicio', async () => {
    // El servicio responde 200 con `exists: false`. No es un error de transporte
    // y no debe presentarse como tal.
    const cliente = clienteCon(
      vi.fn(async () => respuesta({ verification_code: 'FNC-X', exists: false })),
    )

    const resultado = await cliente.constancia('FNC-X')

    expect(resultado.ok).toBe(false)
    if (resultado.ok) return
    expect(resultado.motivo).toBe('CODIGO_NO_ENCONTRADO')
    expect(resultado.detalle).toContain('FNC-X')
  })

  it('trata un 404 como código no encontrado', async () => {
    const cliente = clienteCon(vi.fn(async () => new Response('', { status: 404 })))

    const resultado = await cliente.constancia('FNC-X')

    expect(resultado.ok).toBe(false)
    if (resultado.ok) return
    expect(resultado.motivo).toBe('CODIGO_NO_ENCONTRADO')
  })

  it('no confunde una caída del servicio con un código inválido', async () => {
    // Decirle a alguien que su código no existe cuando en realidad el servicio se
    // cayó es acusar al documento por un problema nuestro.
    const cliente = clienteCon(
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )

    const resultado = await cliente.constancia('FNC-2026-000123')

    expect(resultado.ok).toBe(false)
    if (resultado.ok) return
    expect(resultado.motivo).toBe('SIN_CONEXION')
  })

  it('lee el rechazo por su motivo y no por el mensaje', async () => {
    const cliente = clienteCon(
      vi.fn(async () => respuesta({ motivo: 'UNSUPPORTED_JURISDICTION', mensaje: 'texto' }, 400)),
    )

    const resultado = await cliente.constancia('FNC-X')

    expect(resultado.ok).toBe(false)
    if (resultado.ok) return
    expect(resultado.detalle).toContain('UNSUPPORTED_JURISDICTION')
  })

  it('escapa el código en la ruta', async () => {
    // Un código con barras no puede convertirse en otra ruta.
    const espia = vi.fn(async () => respuesta(CONSTANCIA))
    await clienteCon(espia).constancia('../../admin')

    expect(espia).toHaveBeenCalledWith(
      expect.stringContaining('/v1/verify/..%2F..%2Fadmin'),
      expect.anything(),
    )
  })
})

describe('claves públicas', () => {
  it('devuelve el conjunto publicado', async () => {
    const cliente = clienteCon(vi.fn(async () => respuesta({ keys: [{ kid: 'k1' }] })))

    const resultado = await cliente.clavesPublicas()

    expect(resultado.ok).toBe(true)
    if (!resultado.ok) return
    expect(resultado.datos).toHaveLength(1)
  })

  it('rechaza un documento sin claves utilizables', async () => {
    // Verificar contra un conjunto vacío daría siempre «clave desconocida», que
    // se leería como un acta falsa en lugar de como una publicación rota.
    const cliente = clienteCon(vi.fn(async () => respuesta({ keys: [] })))

    const resultado = await cliente.clavesPublicas()

    expect(resultado.ok).toBe(false)
    if (resultado.ok) return
    expect(resultado.motivo).toBe('RESPUESTA_INESPERADA')
  })
})

describe('contraste entre la constancia y el acta', () => {
  const acta = {
    jurisdiction: 'PY',
    document: { sha256: 'a'.repeat(64), version: 1, code: 'X', closed_at: '2026-01-01T00:00:00Z' },
  } as ContenidoActa

  it('coinciden cuando describen el mismo acto', () => {
    expect(constanciaCoincideConActa(CONSTANCIA, acta)).toBe(true)
  })

  it('discrepan si el documento no es el mismo', () => {
    // Dos fuentes que afirman cosas distintas sobre el mismo acto: una está mal,
    // y ninguna sirve como prueba hasta saber cuál.
    const otra = { ...CONSTANCIA, document_sha256: 'f'.repeat(64) }

    expect(constanciaCoincideConActa(otra, acta)).toBe(false)
  })
})
