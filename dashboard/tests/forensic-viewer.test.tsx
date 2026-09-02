/**
 * @vitest-environment jsdom
 *
 * Visor forense.
 *
 * El foco está en el control de datos personales: abrir una transacción es una
 * consulta, revelar la cédula y las capturas biométricas es un acceso a datos
 * personales, y son dos cosas distintas. Las pruebas fijan esa distinción para
 * que no se pierda en un rediseño.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { cleanup, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import ForensicViewer from '../src/components/ForensicViewer'
import { transaccionDemo } from '../src/lib/mockData'

afterEach(cleanup)

function montar() {
  const auditar = vi.fn()
  const usuario = userEvent.setup()
  render(<ForensicViewer transaccion={transaccionDemo} onAuditar={auditar} />)
  return { auditar, usuario }
}

const CEDULA = transaccionDemo.identity.nationalId

describe('datos personales', () => {
  it('no muestra la cédula completa al abrir la transacción', () => {
    montar()

    // La cédula formateada no debe aparecer en ninguna parte del documento.
    expect(screen.queryByText(/4\.829\.153/)).not.toBeInTheDocument()
    expect(screen.getByText(/\*/)).toBeInTheDocument()
  })

  it('mantiene las capturas biométricas ocultas por defecto', () => {
    montar()

    expect(screen.getAllByText(/contenido protegido/i).length).toBeGreaterThan(0)
    expect(screen.queryByText(/imagen disponible/i)).not.toBeInTheDocument()
  })

  it('revela la cédula solo tras una acción explícita, y la audita', async () => {
    const { auditar, usuario } = montar()

    await usuario.click(screen.getByRole('button', { name: /revelar datos personales/i }))

    expect(screen.getByText(/4\.829\.153/)).toBeInTheDocument()
    expect(screen.getAllByText(/imagen disponible/i).length).toBeGreaterThan(0)
    // Sin registro, la revelación sería indistinguible de no haber ocurrido.
    expect(auditar).toHaveBeenCalledWith('REVEAL_PII', expect.stringContaining(transaccionDemo.transactionId))
  })

  it('vuelve a ocultar los datos sin registrar un segundo acceso', async () => {
    // Ocultar no es un acceso: registrarlo ensuciaría la pista con eventos que
    // no describen ninguna consulta de datos personales.
    const { auditar, usuario } = montar()
    const boton = screen.getByRole('button', { name: /revelar datos personales/i })

    await usuario.click(boton)
    await usuario.click(screen.getByRole('button', { name: /ocultar datos personales/i }))

    expect(screen.queryByText(/4\.829\.153/)).not.toBeInTheDocument()
    expect(auditar.mock.calls.filter(([accion]) => accion === 'REVEAL_PII')).toHaveLength(1)
  })

  it('no filtra la cédula completa en el marcado aunque esté enmascarada', () => {
    // Un `blur` de CSS oculta a la vista pero no al inspector: el dato no debe
    // llegar al DOM hasta que se revele.
    const { container } = render(
      <ForensicViewer transaccion={transaccionDemo} onAuditar={vi.fn()} />,
    )

    expect(container.innerHTML).not.toContain(CEDULA)
  })
})

describe('pestañas de evidencia', () => {
  it('abre en biometría', () => {
    montar()

    const listaPestanias = screen.getByRole('tablist', { name: /evidencias forenses/i })
    expect(within(listaPestanias).getByRole('tab', { name: /biometría/i })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  it('permite recorrer las cuatro secciones de evidencia', async () => {
    const { usuario } = montar()
    const listaPestanias = screen.getByRole('tablist', { name: /evidencias forenses/i })

    for (const nombre of [/red/i, /consentimiento/i, /criptografía y tsa/i]) {
      await usuario.click(within(listaPestanias).getByRole('tab', { name: nombre }))
      expect(within(listaPestanias).getByRole('tab', { name: nombre })).toHaveAttribute(
        'aria-selected',
        'true',
      )
    }
  })
})

describe('descargas', () => {
  /** Espera a que termine la generación simulada de la URL pre-firmada. */
  async function esperarFin(nombre: RegExp) {
    await waitFor(() => expect(screen.getByRole('button', { name: nombre })).toBeEnabled(), {
      timeout: 3000,
    })
  }

  it('registra la descarga del documento firmado antes de generarla', async () => {
    // El registro precede a la entrega: si se anotara después, un fallo en la
    // generación dejaría una descarga solicitada y sin rastro.
    const { auditar, usuario } = montar()

    await usuario.click(screen.getByRole('button', { name: /descargar pdf firmado/i }))

    expect(auditar).toHaveBeenCalledWith('DOWNLOAD_SIGNED_PDF')
    await esperarFin(/descargar pdf firmado/i)
  })

  it('registra la descarga del expediente de evidencias', async () => {
    const { auditar, usuario } = montar()

    await usuario.click(screen.getByRole('button', { name: /descargar expediente/i }))

    expect(auditar).toHaveBeenCalledWith('DOWNLOAD_EVIDENCE_PDF')
    await esperarFin(/descargar expediente/i)
  })

  it('bloquea una segunda descarga mientras hay una en curso', async () => {
    const { usuario } = montar()

    await usuario.click(screen.getByRole('button', { name: /descargar pdf firmado/i }))

    expect(screen.getByRole('button', { name: /descargar expediente/i })).toBeDisabled()
    await esperarFin(/descargar pdf firmado/i)
  })
})
