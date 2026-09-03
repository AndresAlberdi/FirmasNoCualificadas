/**
 * Cliente de la API pública de FNC.
 *
 * Cubre **solo los endpoints que no exigen autenticación**, y no por comodidad:
 * la API B2B se autentica con HMAC sobre un secreto compartido por inquilino, y
 * ese secreto no puede vivir en un navegador. Ponerlo acá lo entregaría a
 * cualquiera que abra las herramientas de desarrollo, junto con la capacidad de
 * firmar peticiones en nombre del inquilino.
 *
 * El expediente forense completo necesita, por lo tanto, una sesión propia del
 * panel —Cognito o el proveedor federado del cliente, con MFA, como describe
 * `docs/diseno/esquema-dashboard-b2b-pscnc.md`— que todavía no existe. Hasta
 * entonces el visor forense se alimenta de datos sintéticos y esta es la única
 * parte del panel que habla con la API real.
 */

import type { ContenidoActa } from './acta'

/** Estados que puede tener una transacción, según el contrato v1. */
export type EstadoTransaccion =
  | 'INITIALIZED'
  | 'SIGNING_COMPLETED'
  | 'FAILED'
  | 'REVOKED'
  | 'COMPROMISED'

/** Respuesta de `GET /v1/verify/{code}`. No lleva ningún dato personal. */
export interface ConstanciaPublica {
  readonly verification_code: string
  readonly exists: boolean
  readonly status?: EstadoTransaccion
  readonly document_sha256?: string
  readonly document_code?: string
  readonly signed_at?: string
  readonly jurisdiction?: string
  /** Norma que da validez a la firma en esa jurisdicción. */
  readonly legal_basis?: string
  readonly service_level?: number
  /** Acta sellada, para verificarla acá mismo sin volver a preguntar. */
  readonly acta_jws?: string
}

/** Clave pública tal como la publica `/.well-known/fnc-keys.json`. */
export interface ClavePublicaPublicada {
  readonly kty: string
  readonly crv: string
  readonly alg: string
  readonly use: string
  readonly kid: string
  readonly x: string
  readonly y: string
}

export type MotivoDeFallo =
  | 'CODIGO_NO_ENCONTRADO'
  | 'RESPUESTA_INESPERADA'
  | 'SIN_CONEXION'

export type Resultado<T> =
  | { readonly ok: true; readonly datos: T }
  | { readonly ok: false; readonly motivo: MotivoDeFallo; readonly detalle: string }

/** Formato del cuerpo de error del contrato v1. */
interface ErrorDeApi {
  readonly motivo?: string
  readonly mensaje?: string
}

export interface OpcionesDelCliente {
  /** Base de la API. Vacío usa el mismo origen, que es lo que hace el proxy. */
  readonly baseUrl?: string
  /** Inyectable para las pruebas; por defecto el `fetch` del navegador. */
  readonly fetchImpl?: typeof globalThis.fetch
}

export class FncPublicClient {
  private readonly baseUrl: string
  private readonly fetchImpl: typeof globalThis.fetch

  constructor(opciones: OpcionesDelCliente = {}) {
    this.baseUrl = recortarBarrasFinales(opciones.baseUrl ?? '')
    this.fetchImpl = opciones.fetchImpl ?? globalThis.fetch.bind(globalThis)
  }

  /**
   * Recupera la constancia pública de una transacción por su código.
   *
   * Un código inexistente no es un error de transporte: el servicio responde con
   * `exists: false`, y se traduce a un motivo propio para que la interfaz no lo
   * confunda con una caída del servicio. Son dos mensajes distintos para el
   * lector: «ese código no corresponde a ninguna firma» y «no pudimos preguntar».
   */
  async constancia(codigo: string): Promise<Resultado<ConstanciaPublica>> {
    const respuesta = await this.pedir(`/v1/verify/${encodeURIComponent(codigo)}`)
    if (!respuesta.ok) return respuesta

    const datos = respuesta.datos as ConstanciaPublica
    if (!datos.exists) {
      return {
        ok: false,
        motivo: 'CODIGO_NO_ENCONTRADO',
        detalle:
          `El código ${codigo} no corresponde a ninguna firma registrada. ` +
          'Puede estar mal transcrito, o pertenecer a otro prestador.',
      }
    }
    return { ok: true, datos }
  }

  /** Descarga el conjunto de claves con las que se sellan las actas. */
  async clavesPublicas(): Promise<Resultado<readonly ClavePublicaPublicada[]>> {
    const respuesta = await this.pedir('/.well-known/fnc-keys.json')
    if (!respuesta.ok) return respuesta

    const cuerpo = respuesta.datos as { keys?: ClavePublicaPublicada[] }
    if (!Array.isArray(cuerpo.keys) || cuerpo.keys.length === 0) {
      return {
        ok: false,
        motivo: 'RESPUESTA_INESPERADA',
        detalle: 'El documento de claves no contiene ningún conjunto utilizable.',
      }
    }
    return { ok: true, datos: cuerpo.keys }
  }

  private async pedir(ruta: string): Promise<Resultado<unknown>> {
    let respuesta: Response
    try {
      respuesta = await this.fetchImpl(`${this.baseUrl}${ruta}`, {
        headers: { Accept: 'application/json' },
      })
    } catch (error) {
      return {
        ok: false,
        motivo: 'SIN_CONEXION',
        detalle: error instanceof Error ? error.message : 'No se pudo contactar al servicio.',
      }
    }

    if (respuesta.status === 404) {
      return {
        ok: false,
        motivo: 'CODIGO_NO_ENCONTRADO',
        detalle: 'El servicio no reconoce ese código de verificación.',
      }
    }

    if (!respuesta.ok) {
      // Los rechazos del contrato se leen por `motivo`, nunca por el mensaje.
      const cuerpo = await leerJsonSinRomper(respuesta)
      const motivo = (cuerpo as ErrorDeApi | null)?.motivo
      return {
        ok: false,
        motivo: 'RESPUESTA_INESPERADA',
        detalle: motivo
          ? `El servicio rechazó la consulta con el motivo ${motivo}.`
          : `El servicio respondió ${respuesta.status}.`,
      }
    }

    const cuerpo = await leerJsonSinRomper(respuesta)
    if (cuerpo === null) {
      return {
        ok: false,
        motivo: 'RESPUESTA_INESPERADA',
        detalle: 'La respuesta del servicio no es JSON válido.',
      }
    }
    return { ok: true, datos: cuerpo }
  }
}

async function leerJsonSinRomper(respuesta: Response): Promise<unknown | null> {
  try {
    return (await respuesta.json()) as unknown
  } catch {
    return null
  }
}

function recortarBarrasFinales(url: string): string {
  // Recorrido y no `replace(/\/+$/, "")`: un cuantificador anclado al final
  // obliga al motor a reintentar desde cada posición, y cuesta tiempo cuadrático.
  let fin = url.length
  while (fin > 0 && url[fin - 1] === '/') fin -= 1
  return url.slice(0, fin)
}

/** Lo que el acta afirma y la constancia también: si difieren, algo no cierra. */
export function constanciaCoincideConActa(
  constancia: ConstanciaPublica,
  acta: ContenidoActa,
): boolean {
  return (
    constancia.document_sha256 === acta.document.sha256 &&
    constancia.jurisdiction === acta.jurisdiction
  )
}
