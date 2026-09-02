/**
 * Verificación del acta sellada en el navegador.
 *
 * Las actas de prueba se **sellan de verdad** con WebCrypto, con una clave
 * generada en cada caso: no hay sobres escritos a mano. Es la única forma de que
 * la prueba diga algo — un JWS inventado a mano solo comprobaría que el
 * verificador lee cadenas.
 *
 * Todos los datos son sintéticos.
 */
import { beforeAll, describe, expect, it } from 'vitest'
import {
  VERSION_ACTA_SOPORTADA,
  esArtefactoDePrueba,
  tieneFechaCierta,
  verificarActa,
} from '../src/lib/acta'
import type { ClavePublicaJwk, ContenidoActa } from '../src/lib/acta'

const KID = 'alias/fnc/prod/aseguradora-py/acta-seal/v1'

function aBase64Url(datos: Uint8Array | string): string {
  const bytes = typeof datos === 'string' ? new TextEncoder().encode(datos) : datos
  let binario = ''
  for (const b of bytes) binario += String.fromCharCode(b)
  return btoa(binario).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** Sella un acta como lo hace el servicio: ES256 sobre `cabecera.contenido`. */
async function sellar(
  contenido: Record<string, unknown>,
  clave: CryptoKeyPair,
  kid = KID,
): Promise<string> {
  const cabecera = aBase64Url(JSON.stringify({ alg: 'ES256', typ: 'JOSE', kid }))
  const cuerpo = aBase64Url(JSON.stringify(contenido))
  const firma = await crypto.subtle.sign(
    { name: 'ECDSA', hash: 'SHA-256' },
    clave.privateKey,
    new TextEncoder().encode(`${cabecera}.${cuerpo}`),
  )
  return `${cabecera}.${cuerpo}.${aBase64Url(new Uint8Array(firma))}`
}

async function publicarClave(clave: CryptoKeyPair, kid = KID): Promise<ClavePublicaJwk> {
  const jwk = (await crypto.subtle.exportKey('jwk', clave.publicKey)) as {
    kty: string
    crv: string
    x: string
    y: string
  }
  return { kty: jwk.kty, crv: jwk.crv, alg: 'ES256', use: 'sig', kid, x: jwk.x, y: jwk.y }
}

type ActaCruda = Record<string, unknown>

function contenidoDeEjemplo(extra: ActaCruda = {}): ActaCruda {
  return {
    acta_version: VERSION_ACTA_SOPORTADA,
    tenant_id: 'aseguradora-py',
    transaction_id: 'c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb',
    jurisdiction: 'PY',
    service_level: 1,
    document: {
      sha256: 'a'.repeat(64),
      version: 2,
      code: 'PROP-2026-000123',
      closed_at: '2026-09-02T14:30:00Z',
    },
    evidence_sha256: 'b'.repeat(64),
    sealed_at: '2026-09-02T14:31:15Z',
    tenant_reference: 'EXP-99887',
    ...extra,
  }
}

describe('verificación del acta sellada', () => {
  let clave: CryptoKeyPair
  let claves: ClavePublicaJwk[]

  beforeAll(async () => {
    clave = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
      'sign',
      'verify',
    ])) as CryptoKeyPair
    claves = [await publicarClave(clave)]
  })

  it('acepta un acta auténtica y devuelve su contenido', async () => {
    const jws = await sellar(contenidoDeEjemplo(), clave)

    const resultado = await verificarActa(jws, claves)

    expect(resultado.valido).toBe(true)
    if (!resultado.valido) return
    expect(resultado.contenido.transaction_id).toBe('c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb')
    expect(resultado.contenido.document.sha256).toBe('a'.repeat(64))
    expect(resultado.kid).toBe(KID)
  })

  it('rechaza un acta cuyo contenido fue alterado', async () => {
    // La propiedad que hace del acta una prueba y no una declaración.
    const jws = await sellar(contenidoDeEjemplo(), clave)
    const [cabecera, , firma] = jws.split('.')
    const original = contenidoDeEjemplo()
    const documento = original.document as Record<string, unknown>
    const adulterado = aBase64Url(
      JSON.stringify(contenidoDeEjemplo({ document: { ...documento, sha256: 'f'.repeat(64) } })),
    )

    const resultado = await verificarActa(`${cabecera}.${adulterado}.${firma}`, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('FIRMA_INVALIDA')
  })

  it('rechaza un acta sellada con otra clave', async () => {
    // Un tercero no puede hacer pasar su acta por una nuestra.
    const otra = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
      'sign',
      'verify',
    ])) as CryptoKeyPair
    const jws = await sellar(contenidoDeEjemplo(), otra)

    const resultado = await verificarActa(jws, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('FIRMA_INVALIDA')
  })

  it('rechaza un acta cuya clave no está publicada', async () => {
    const otra = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
      'sign',
      'verify',
    ])) as CryptoKeyPair
    const jws = await sellar(contenidoDeEjemplo(), otra, 'alias/fnc/prod/otro-tenant/acta-seal/v1')

    const resultado = await verificarActa(jws, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('CLAVE_DESCONOCIDA')
    expect(resultado.detalle).toContain('otro-tenant')
  })

  it('rechaza un sobre mal formado', async () => {
    const resultado = await verificarActa('esto.no-es-un-acta', claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('SOBRE_MAL_FORMADO')
  })

  it('rechaza un algoritmo distinto de ES256', async () => {
    // Defensa contra el sobre con `alg: none`, que es el ataque clásico sobre JWS.
    const cabecera = aBase64Url(JSON.stringify({ alg: 'none', typ: 'JOSE', kid: KID }))
    const cuerpo = aBase64Url(JSON.stringify(contenidoDeEjemplo()))

    const resultado = await verificarActa(`${cabecera}.${cuerpo}.`, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('ALGORITMO_NO_SOPORTADO')
  })

  it('rechaza una versión de formato que no entiende', async () => {
    // Interpretar a medias un formato desconocido es peor que rechazarlo.
    const jws = await sellar(contenidoDeEjemplo({ acta_version: 99 }), clave)

    const resultado = await verificarActa(jws, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('VERSION_DESCONOCIDA')
  })

  it('comprueba la versión después de la firma y no antes', async () => {
    // Leer el contenido de un sobre sin verificar es leer una afirmación de
    // quien lo envió: una versión inaceptable en un sobre falso debe fallar por
    // la firma, no por la versión.
    const otra = (await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, [
      'sign',
      'verify',
    ])) as CryptoKeyPair
    const jws = await sellar(contenidoDeEjemplo({ acta_version: 99 }), otra)

    const resultado = await verificarActa(jws, claves)

    expect(resultado.valido).toBe(false)
    if (resultado.valido) return
    expect(resultado.motivo).toBe('FIRMA_INVALIDA')
  })
})

describe('lectura del acta verificada', () => {
  it('distingue un artefacto de desarrollo de uno real', () => {
    const desarrollo = {
      ...contenidoDeEjemplo({ environment: 'dev', not_valid_for_production: true }),
    } as unknown as ContenidoActa
    const produccion = contenidoDeEjemplo() as unknown as ContenidoActa

    expect(esArtefactoDePrueba(desarrollo)).toBe(true)
    expect(esArtefactoDePrueba(produccion)).toBe(false)
  })

  it('solo reconoce fecha cierta con una autoridad cualificada', () => {
    // Un sello de una TSA de pruebas acredita que el sistema funciona, no la
    // fecha del acto.
    const conTsaDePrueba = contenidoDeEjemplo({
      timestamp: { token_sha256: 'c'.repeat(64), authority: 'TSA de Pruebas', qualified: false },
    }) as unknown as ContenidoActa
    const conTsaCualificada = contenidoDeEjemplo({
      timestamp: { token_sha256: 'c'.repeat(64), authority: 'Confirma S.A.', qualified: true },
    }) as unknown as ContenidoActa

    expect(tieneFechaCierta(conTsaDePrueba)).toBe(false)
    expect(tieneFechaCierta(conTsaCualificada)).toBe(true)
  })

  it('un acta de nivel 1 no declara fecha cierta', () => {
    // En el nivel 1 no hay sello de tiempo: lo que prueba el acto es el acta.
    expect(tieneFechaCierta(contenidoDeEjemplo() as unknown as ContenidoActa)).toBe(false)
  })
})
