/**
 * Utilidades de presentación.
 *
 * El enmascarado es lo que hace que abrir una transacción no sea, por sí solo,
 * un acceso a datos personales: por eso se prueba el caso corto, donde una
 * implementación descuidada revelaría el dato entero.
 */
import { describe, expect, it } from 'vitest'
import {
  abreviarHash,
  colorPuntajeBiometrico,
  enmascararCedula,
  enmascararTelefono,
  formatearCedula,
  formatearFechaPy,
  porcentaje,
} from '../src/lib/format'

describe('cédula', () => {
  it('agrupa los miles con puntos', () => {
    expect(formatearCedula('4829153')).toBe('4.829.153')
    expect(formatearCedula('123')).toBe('123')
  })

  it('deja visibles solo los primeros cuatro dígitos', () => {
    expect(enmascararCedula('4829153')).toBe('4.829.***')
  })

  it('oculta por completo una cédula demasiado corta para enmascarar', () => {
    // El control se mide sobre los dígitos. Midiéndolo sobre la cadena ya
    // formateada, los propios separadores de miles la hacían superar el umbral
    // y la cédula se mostraba entera.
    expect(enmascararCedula('123')).toBe('***')
    expect(enmascararCedula('1234')).toBe('*****')
    expect(enmascararCedula('482915')).toBe('*******')
  })

  it('nunca deja a la vista más dígitos de los que oculta', () => {
    for (const cedula of ['1', '12', '123', '1234', '12345', '123456', '1234567', '12345678']) {
      const visibles = enmascararCedula(cedula).replace(/\D/g, '').length
      expect(visibles).toBeLessThanOrEqual(Math.max(0, cedula.length - 3))
    }
  })
})

describe('teléfono', () => {
  it('conserva prefijo y últimos tres dígitos', () => {
    expect(enmascararTelefono('+595981123456')).toBe('+595 981 ***456')
  })

  it('oculta por completo un número demasiado corto', () => {
    expect(enmascararTelefono('12345')).toBe('***')
  })
})

describe('hash', () => {
  it('elide el centro de un hash largo', () => {
    const hash = 'a'.repeat(64)
    expect(abreviarHash(hash)).toBe(`${'a'.repeat(12)}…${'a'.repeat(12)}`)
  })

  it('no toca un hash que ya es corto', () => {
    expect(abreviarHash('abc123')).toBe('abc123')
  })
})

describe('fecha', () => {
  it('acompaña la hora local con la referencia UTC', () => {
    // La hora local es legible; la UTC es la que se compara contra la evidencia.
    const salida = formatearFechaPy('2026-08-22T21:43:23Z')
    expect(salida).toContain('(PY)')
    expect(salida).toContain('2026-08-22T21:43:23Z')
  })

  it('devuelve un guion ante una fecha ausente o inválida', () => {
    expect(formatearFechaPy(null)).toBe('—')
    expect(formatearFechaPy('no es una fecha')).toBe('—')
  })
})

describe('puntaje biométrico', () => {
  it('aplica los umbrales de la política del prestador', () => {
    expect(colorPuntajeBiometrico(0.985)).toContain('emerald')
    expect(colorPuntajeBiometrico(0.92)).toContain('amber')
    expect(colorPuntajeBiometrico(0.7)).toContain('rose')
  })

  it('formatea la proporción como porcentaje con dos decimales', () => {
    expect(porcentaje(0.985)).toBe('98.50 %')
  })
})
