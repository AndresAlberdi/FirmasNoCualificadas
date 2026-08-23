import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

const contenedor = document.getElementById('root')
if (!contenedor) {
  throw new Error('No se encontró el nodo raíz de la aplicación')
}

ReactDOM.createRoot(contenedor).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
