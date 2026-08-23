/** Utilidades de presentación. Ninguna realiza llamadas de red. */

/** Cédula paraguaya con separadores de miles: 4829153 → 4.829.153 */
export function formatearCedula(cedula: string): string {
  return cedula.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
}

/**
 * Enmascara la cédula para su visualización por defecto.
 * La revelación completa exige una acción explícita que queda auditada.
 */
export function enmascararCedula(cedula: string): string {
  const formateada = formatearCedula(cedula)
  if (formateada.length <= 4) return '*'.repeat(formateada.length)
  return formateada.slice(0, 5) + formateada.slice(5).replace(/\d/g, '*')
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
