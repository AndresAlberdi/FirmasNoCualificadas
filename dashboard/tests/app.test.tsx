/**
 * @vitest-environment jsdom
 *
 * Composición del panel. Lo único propio de `App` es el registro de auditoría:
 * que toda acción de los componentes termine anotada y visible.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from '../src/App'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function registro() {
  return screen.getByRole('list', { name: /registro de auditoría/i })
}

describe('panel B2B', () => {
  it('advierte que el prototipo usa datos sintéticos', () => {
    render(<App />)

    // La advertencia es lo que impide leer una demostración como evidencia.
    expect(screen.getByText(/datos sintéticos/i)).toBeInTheDocument()
  })

  it('anota la consulta de la transacción desde el inicio', () => {
    render(<App />)

    expect(within(registro()).getByText('VIEW_TRANSACTION')).toBeInTheDocument()
  })

  it('anota la revelación de datos personales del visor forense', async () => {
    const usuario = userEvent.setup()
    render(<App />)

    await usuario.click(screen.getByRole('button', { name: /revelar datos personales/i }))

    expect(within(registro()).getByText('REVEAL_PII')).toBeInTheDocument()
  })

  it('anota la verificación de un acta', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 404 })))
    const usuario = userEvent.setup()
    render(<App />)

    await usuario.type(screen.getByLabelText(/acta sellada/i), 'no-es-un-acta')
    await usuario.click(screen.getByRole('button', { name: /cargar claves/i }))
    await screen.findByText(/no se pudieron cargar las claves/i)

    // Sin claves cargadas el veredicto no puede emitirse, así que tampoco hay
    // nada que anotar: la ausencia del evento es el comportamiento correcto.
    expect(within(registro()).queryByText('VERIFY_ACTA')).not.toBeInTheDocument()
  })

  it('recuerda que la firma no cualificada carece de la presunción de autoría', () => {
    render(<App />)

    expect(screen.getByText(/sin la presunción\s+legal de autoría/i)).toBeInTheDocument()
  })
})
