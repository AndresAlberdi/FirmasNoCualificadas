/**
 * Verificación del acta sellada **en el navegador**, sin backend.
 *
 * Es la pieza que da sentido al nivel 1 (ADR-0007): ahí el documento no se
 * modifica, así que lo único que prueba el acto de firma es el acta. Un acta que
 * solo el emisor sabe comprobar no traslada confianza, la concentra — de modo
 * que la comprobación tiene que poder hacerla quien recibió el documento, con
 * las claves públicas y nada más.
 *
 * Se usa **WebCrypto**, que viene en el navegador: sin librerías de terceros, sin
 * llamadas a nuestra API y sin confiar en este panel. El mismo código funciona
 * pegado en la consola de cualquier navegador, que es exactamente la propiedad
 * que hace verificable un acta.
 *
 * Lo que esta verificación prueba y lo que no:
 *
 * - **Prueba** que el contenido del acta no se alteró desde que se selló, y que
 *   la selló quien tiene la clave privada correspondiente a la pública publicada.
 * - **No prueba** que los hechos que el acta afirma sean ciertos. El acta dice
 *   que el tenant verificó la identidad con determinada política; que esa
 *   verificación fuera correcta es responsabilidad del tenant (ADR-0009).
 */

/** Clave pública en formato JWK, tal como la publica `/.well-known/fnc-keys.json`. */
export interface ClavePublicaJwk {
  readonly kty: string
  readonly crv: string
  readonly alg: string
  readonly use: string
  readonly kid: string
  readonly x: string
  readonly y: string
}

export interface DocumentoDelActa {
  readonly sha256: string
  readonly version: number
  readonly code: string
  readonly closed_at: string
}

/** Contenido del acta, tal como viaja en el sobre JWS. */
export interface ContenidoActa {
  readonly acta_version: number
  readonly tenant_id: string
  readonly transaction_id: string
  readonly jurisdiction: string
  readonly service_level: number
  readonly document: DocumentoDelActa
  readonly evidence_sha256: string
  readonly sealed_at: string
  readonly tenant_reference?: string
  readonly signed_document_sha256?: string
  readonly signer_certificate_serial?: string
  readonly timestamp?: {
    readonly token_sha256: string
    readonly authority: string
    readonly qualified: boolean
  }
  /** Presente solo fuera de producción. Su ausencia es la señal de que es real. */
  readonly environment?: string
  readonly not_valid_for_production?: boolean
}

export type ResultadoVerificacion =
  | { readonly valido: true; readonly contenido: ContenidoActa; readonly kid: string }
  | { readonly valido: false; readonly motivo: MotivoActaInvalida; readonly detalle: string }

export type MotivoActaInvalida =
  | 'SOBRE_MAL_FORMADO'
  | 'ALGORITMO_NO_SOPORTADO'
  | 'CLAVE_DESCONOCIDA'
  | 'FIRMA_INVALIDA'
  | 'VERSION_DESCONOCIDA'

/** Versión del formato de acta que este verificador entiende. */
export const VERSION_ACTA_SOPORTADA = 1

// El buffer se reserva explícitamente como `ArrayBuffer`: WebCrypto no acepta
// vistas sobre `SharedArrayBuffer`, y TypeScript lo exige desde la 5.7.
function desdeBase64Url(texto: string): Uint8Array<ArrayBuffer> {
  const base64 = texto.replace(/-/g, '+').replace(/_/g, '/')
  const relleno = base64.padEnd(base64.length + ((4 - (base64.length % 4)) % 4), '=')
  const binario = atob(relleno)
  const bytes = new Uint8Array(new ArrayBuffer(binario.length))
  for (let i = 0; i < binario.length; i += 1) {
    bytes[i] = binario.charCodeAt(i)
  }
  return bytes
}

function textoDesdeBase64Url(texto: string): string {
  return new TextDecoder().decode(desdeBase64Url(texto))
}

/**
 * Verifica un acta sellada contra un conjunto de claves públicas.
 *
 * El `kid` de la cabecera dice cuál usar, que es lo que hace posible una
 * rotación: durante el solapamiento conviven dos versiones, y un acta vieja se
 * sigue verificando con la clave con la que se selló.
 */
export async function verificarActa(
  jws: string,
  claves: readonly ClavePublicaJwk[],
): Promise<ResultadoVerificacion> {
  const partes = jws.split('.')
  if (partes.length !== 3) {
    return {
      valido: false,
      motivo: 'SOBRE_MAL_FORMADO',
      detalle: 'Un sobre JWS compacto tiene tres partes separadas por puntos.',
    }
  }

  const [cabeceraB64, contenidoB64, firmaB64] = partes as [string, string, string]

  let cabecera: { alg?: string; kid?: string }
  try {
    cabecera = JSON.parse(textoDesdeBase64Url(cabeceraB64))
  } catch {
    return {
      valido: false,
      motivo: 'SOBRE_MAL_FORMADO',
      detalle: 'La cabecera del sobre no es JSON válido.',
    }
  }

  if (cabecera.alg !== 'ES256') {
    return {
      valido: false,
      motivo: 'ALGORITMO_NO_SOPORTADO',
      detalle: `El acta declara el algoritmo ${cabecera.alg ?? '(ninguno)'} y solo se admite ES256.`,
    }
  }

  const clave = claves.find((k) => k.kid === cabecera.kid)
  if (!clave) {
    return {
      valido: false,
      motivo: 'CLAVE_DESCONOCIDA',
      detalle:
        `El acta se selló con la clave ${cabecera.kid ?? '(sin identificar)'}, que no está ` +
        'entre las publicadas. Puede ser de otro prestador, o de una versión ya retirada.',
    }
  }

  const clavePublica = await crypto.subtle.importKey(
    'jwk',
    { kty: clave.kty, crv: clave.crv, x: clave.x, y: clave.y, ext: true },
    { name: 'ECDSA', namedCurve: 'P-256' },
    false,
    ['verify'],
  )

  const entradaFirmada = new TextEncoder().encode(`${cabeceraB64}.${contenidoB64}`)
  const firmaValida = await crypto.subtle.verify(
    { name: 'ECDSA', hash: 'SHA-256' },
    clavePublica,
    desdeBase64Url(firmaB64),
    entradaFirmada,
  )

  if (!firmaValida) {
    return {
      valido: false,
      motivo: 'FIRMA_INVALIDA',
      detalle:
        'La firma no corresponde al contenido: el acta fue alterada después de sellarse, ' +
        'o no la selló quien dice haberla sellado.',
    }
  }

  const contenido: ContenidoActa = JSON.parse(textoDesdeBase64Url(contenidoB64))

  // La comprobación de versión va **después** de verificar la firma: leer el
  // contenido de un sobre sin verificar es leer una afirmación de quien lo envió.
  if (contenido.acta_version !== VERSION_ACTA_SOPORTADA) {
    return {
      valido: false,
      motivo: 'VERSION_DESCONOCIDA',
      detalle:
        `El acta usa el formato versión ${contenido.acta_version} y este verificador ` +
        `entiende la ${VERSION_ACTA_SOPORTADA}. Interpretarla a medias sería peor que ` +
        'no interpretarla.',
    }
  }

  return { valido: true, contenido, kid: clave.kid }
}

/** Un acta de desarrollo nunca debe presentarse como prueba. */
export function esArtefactoDePrueba(contenido: ContenidoActa): boolean {
  return contenido.not_valid_for_production === true || contenido.environment !== undefined
}

/** El sello de tiempo solo aporta fecha cierta si lo emitió una autoridad cualificada. */
export function tieneFechaCierta(contenido: ContenidoActa): boolean {
  return contenido.timestamp?.qualified === true
}
