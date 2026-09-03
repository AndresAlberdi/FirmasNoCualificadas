/// <reference types="vitest/config" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // El panel nunca llama a AWS directamente: todo pasa por la API B2B.
      '/v1': {
        target: process.env.VITE_API_BASE_URL ?? 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false, // no se publican mapas de origen del panel administrativo
  },
  test: {
    // El entorno por defecto es `node`, donde WebCrypto está disponible tal como
    // lo estará en el navegador. Las pruebas de componente piden `jsdom` con la
    // anotación `@vitest-environment` en su cabecera.
    environment: 'node',
    setupFiles: ['./tests/preparacion.ts'],
    coverage: {
      provider: 'v8',
      // Se mide **todo** `src`, no solo lo que las pruebas llegan a importar. Con
      // el comportamiento por defecto, un archivo sin ninguna prueba no aparece
      // en el informe: la cobertura saldría alta justamente por no probarlo.
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/main.tsx', // arranque de React: tres líneas sin lógica propia
        'src/lib/mockData.ts', // datos sintéticos del prototipo
        'src/lib/types.ts', // solo declaraciones de tipos
      ],
    },
  },
})
