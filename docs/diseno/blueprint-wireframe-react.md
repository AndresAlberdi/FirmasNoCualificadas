# Guía de Implementación UI: Wireframe Interactivo del Folleto Forense (React + Tailwind CSS)

Este documento contiene la especificación de diseño visual, la distribución espacial de componentes (wireframe) y el código base estructurado para que **Claude AI** genere un prototipo interactivo de alta fidelidad del **Folleto Forense** (SaaS B2B).

---

## 1. Distribución Espacial del Dashboard (Vista de Escritorio)

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────────┐
│  [Logo PSCNC]  Folleto Forense - Portal de Evidencias B2B                   [Usuario Admin B2B (MFA)] │
├──────────────────────────────────────┬───────────────────────────────────────────────────────────────┤
│ PANEL IZQUIERDO: DETALLES TRANSACCION│ PANEL DERECHO: TABS DE EVIDENCIAS FORENSES                     │
│                                      │                                                               │
│ ┌──────────────────────────────────┐ │  ┌──────────────┐ ┌────────┐ ┌────────────────┐ ┌───────────┐ │
│ │ ID: 9b1deb4d-3b7d-4bad-9bdd...   │ │  │ 1. BIOMETRÍA │ │ 2. RED │ │ 3. CONSENTIMTO │ │ 4. CRIPTO │ │
│ │ Estado: [ COMPLETED ] (PAdES-T)   │ │  └──────────────┘ └────────┘ └────────────────┘ └───────────┘ │
│ ├──────────────────────────────────┤ │ ┌───────────────────────────────────────────────────────────┐ │
│ │ CLIENTE B2B: Aseguradora PY      │ │ │ VISTA ACTIVA: BIOMETRÍA FACIAL                            │ │
│ │ FECHA: 2026-08-22 21:43:35 UTC   │ │ │                                                           │ │
│ ├──────────────────────────────────┤ │ │  ┌───────────────────────┐     ┌───────────────────────┐  │ │
│ │ DOCUMENTO ORIGINAL:              │ │ │  │ Foto Cédula (OCR)     │     │ Selfie Live (Liveness)│  │ │
│ │ Hash: e3b0c44298fc1c149afb...    │ │ │  │                       │     │                       │  │ │
│ │ DOCUMENTO FIRMADO:               │ │ │  │ [ Foto Extraída ]     │     │ [ Foto Capturada ]    │  │ │
│ │ Hash: a4f4944be6fc3a1599bf...    │ │ │  └───────────────────────┘     └───────────────────────┘  │ │
│ ├──────────────────────────────────┤ │ │                 [ Match Score: 98.5% (Aprobado) ]         │ │
│ │ ACCIONES:                        │ │ │                                                           │ │
│ │ [ DESCARGAR PDF FIRMADO ]        │ │ │  Detalles del OCR:                                        │ │
│ │ [ DESCARGAR AUDIT TRAIL PDF ]    │ │ │  - Nombres: Juan Pérez      - Cédula: 1.234.567           │ │
│ └──────────────────────────────────┘ │ └───────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────┴───────────────────────────────────────────────────────────────┘
```

---

## 2. Prompt "Copiar y Pegar" para Claude AI (Generación del Componente React)

Copia y pega el siguiente prompt en Claude AI para obtener el código completo del componente frontend interactivo utilizando **React**, **TypeScript** y **Tailwind CSS**:

```text
Actúa como un Ingeniero Frontend Principal especializado en UI/UX y seguridad. Utilizando React (TypeScript), Tailwind CSS y la librería de íconos Lucide-react, genera un componente interactivo de una sola página (SPA) que sirva como el "Folleto Forense / Visualizador de Evidencias" para una plataforma SaaS de Firma Electrónica No Cualificada en Paraguay.

El diseño debe ser extremadamente limpio, profesional, con temática oscura de alta tecnología (slate-900 / zinc-900) y acentos azul corporativo (blue-600) y verde esmeralda (emerald-500) para estados aprobados.

Requisitos de la interfaz y comportamiento:
1. Barra superior: Nombre de la plataforma, logo conceptual, estatus de conexión mTLS activa, y perfil del usuario autenticado con badge de "MFA Activo".
2. Layout de dos columnas:
   - Columna Izquierda (Sidebar de Metadatos): Información resumida de la transacción (ID, Hash SHA-256 del PDF original y firmado, timestamp RFC 3161 de la TSA paraguaya, y botones de acción simulados con estados "hover" para descargar el PDF firmado y el Audit Trail consolidado).
   - Columna Derecha (Panel de Evidencias con Tabs):
     Debe permitir navegar interactivamente entre 4 pestañas:
     - Tab 1: Biometría Facial. Muestra una comparativa lado a lado (Foto de la Cédula extraída por OCR vs Selfie en vivo) con un gráfico circular o barra de progreso que indique "98.5% Match Biométrico" y un badge de "Prueba de Vida (Liveness): Aprobada". Incluye los datos textuales del OCR (Nombres, Apellidos, Nro de Cédula, Fecha de Nacimiento).
     - Tab 2: Datos de Red. Muestra un log técnico estructurado con la IP pública, puerto, cabecera User-Agent, y un mapa conceptual vectorizado (puedes simularlo con SVG) indicando la geolocalización física aproximada en Asunción, Paraguay.
     - Tab 3: Consentimiento y Mensajería. Muestra la traza del OTP enviado por WhatsApp/SMS. Una línea de tiempo que indique: 1. Código OTP enviado a +595981xxxxxx (Timestamp); 2. Código recibido y digitado correctamente; 3. Hash del texto de consentimiento legal firmado ("Yo, Juan Pérez, acepto firmar de manera electrónica no cualificada el contrato...").
     - Tab 4: Criptografía y TSA. Muestra la cadena de confianza del certificado efímero X.509 v3 del usuario (CN, serialNumber en formato "PY-1234567", Key Usage de No Repudio) y el bloque de firma PAdES con el sello cualificado de tiempo (TSA) emitido por un Prestador Cualificado de Paraguay (ej. Confirma S.A. o VIT S.A.).

Genera un único archivo de React que contenga toda la lógica de estados de los tabs, datos estáticos realistas que simulen una transacción paraguaya real, e interactividad pulida para que pueda ser visualizado directamente en un entorno como Vite o Next.js.
```

---

## 3. Guía de Interacción y Validaciones de Seguridad en la UI

Al implementar el componente generado por Claude AI en tu entorno de desarrollo, asegúrate de aplicar las siguientes directivas de diseño:

1. **Enmascaramiento Dinámico de PII (Datos de Identidad):**
   * Por defecto, el número de cédula debe mostrarse con formato protegido (ej. `1.23*.***`) y la imagen de la Cédula debe tener un filtro blur moderado que requiera que el administrador haga clic en un icono de "ojo" (revelado de datos) para ver la información en claro.
   * Cada acción de revelado debe disparar un evento de auditoría en tu log de AWS CloudWatch.
2. **Estados de Carga (Loading States):**
   * El botón "Descargar PDF Firmado" y "Descargar Audit Trail" debe simular un estado de carga asíncrona mediante un spinner de Tailwind y deshabilitar temporalmente la acción mientras se genera la URL firmada de S3.
3. **Indicador de Integridad del Documento:**
   * Agrega un banner superior en verde cuando los hashes correspondan estrictamente con la base de datos de DynamoDB, o un banner rojo parpadeante con alerta de SecOps si se detecta cualquier discrepancia entre el hash del PDF cargado y el hash de auditoría.
