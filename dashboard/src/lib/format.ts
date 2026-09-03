/** Utilidades de presentación. Ninguna realiza llamadas de red. */

/** Cédula paraguaya con separadores de miles: 4829153 → 4.829.153 */
export function formatearCedula(cedula: string): string {
  return cedula.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

/** Dígitos que quedan a la vista, y cuántos deben permanecer ocultos como mínimo. */
const DIGITOS_VISIBLES = 4
const DIGITOS_OCULTOS_MINIMOS = 3

/**
 * Enmascara la cédula para su visualización por defecto.
 * La revelación completa exige una acción explícita que queda auditada.
 *
 * El umbral se mide sobre los **dígitos**, no sobre la cadena ya formateada: los
 * separadores de miles la alargan, de modo que una cédula corta superaba el
 * control por los puntos que ella misma agregaba y terminaba mostrándose entera.
 * Cuando no quedan suficientes dígitos por ocultar, se enmascara todo: revelar
 * casi toda una cédula equivale a revelarla.
 */
export function enmascararCedula(cedula: string): string {
  const digitos = cedula.replace(/\D/g, '')
  const formateada = formatearCedula(cedula)

  if (digitos.length < DIGITOS_VISIBLES + DIGITOS_OCULTOS_MINIMOS) {
    return '*'.repeat(formateada.length)
  }

  let vistos = 0
  return Array.from(formateada, (caracter) => {
    if (!/\d/.test(caracter)) return caracter
    vistos += 1
    return vistos <= DIGITOS_VISIBLES ? caracter : '*'
  }).join('')
}

/** Teléfono E.164 parcialmente oculto: +595981123456 → +595 981 ***456 */
export function enmascararTelefono(numero: string): string {
  if (numero.length < 7) return '***'
  return `${numero.slice(0, 4)} ${numero.slice(4, 7)} ***${numero.slice(-3)}`
}

/** Muestra el inicio y el final de un hash largo, con el centro elidido. */
export function abreviarHash(hash: string, visibles = 12): string {
  if (hash.length <= visibles * 2) return hash
  return `${hash.slice(0, visibles)}…${hash.slice(-visibles)}`
}

/** Fecha en hora local de Paraguay, con la referencia UTC explícita. */
export function formatearFechaPy(iso: string | null): string {
  if (!iso) return '—'
  const fecha = new Date(iso)
  if (Number.isNaN(fecha.getTime())) return '—'
  const local = new Intl.DateTimeFormat('es-PY', {
    dateStyle: 'medium',
    timeStyle: 'medium',
    timeZone: 'America/Asuncion',
  }).format(fecha)
  return `${local} (PY) · ${fecha.toISOString().replace('.000', '')}`
}

/** Semáforo del puntaje biométrico según la política del prestador. */
export function colorPuntajeBiometrico(score: number): string {
  if (score >= 0.95) return 'text-emerald-400'
  if (score >= 0.9) return 'text-amber-400'
  return 'text-rose-400'
}

export function porcentaje(valor: number): string {
  return `${(valor * 100).toFixed(2)} %`
}
