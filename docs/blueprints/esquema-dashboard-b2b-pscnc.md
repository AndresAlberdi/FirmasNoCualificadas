# Especificación de Interfaz: Panel de Control SaaS B2B para Monitoreo de Firmas y Evidencias Forenses (PSCNC)

## 1. Introducción y Propósito de la Interfaz
Este documento establece las especificaciones técnicas, funcionales y de seguridad para el diseño y desarrollo del **Panel de Control SaaS B2B (SaaS Dashboard)**. Esta interfaz está destinada a los clientes corporativos de tu plataforma de firma electrónica no cualificada en Paraguay (PSCNC). 

El propósito del dashboard es doble:
1. **Operativo:** Permitir a los administradores B2B rastrear, buscar y monitorear el ciclo de vida de los procesos de firma e integraciones API en tiempo real.
2. **Legal e Informático Forense:** Proveer a los departamentos jurídicos, oficiales de cumplimiento y peritos informáticos de tus clientes un portal seguro para verificar las evidencias forenses recolectadas durante el onboarding y firma de un usuario (para responder con éxito a eventuales desconocimientos de firmas en juicios civiles bajo la **Ley N.º 6822/2021**).

---

## 2. Arquitectura de Navegación y Estructura del Dashboard

El dashboard se organiza en un menú lateral estático (*Sidebar*) con acceso controlado según el rol del usuario corporativo:

```
[ Panel B2B ] ──┬──► [ 1. Vista General (Métricas Operativas) ]
                ├──► [ 2. Explorador de Transacciones (Historial) ]
                │         └──► [ Vista Detallada de Transacción ]
                │                  ├──► Visualizador de Onboarding Biométrico
                │                  ├──► Logs de Red y Geolocalización
                │                  ├──► Evidencia de Consentimiento (OTP)
                │                  └──► Descarga Segura de Documentos y Evidencias
                ├──► [ 3. Configuración del Desarrollador (API & Webhooks) ]
                └──► [ 4. Logs de Auditoría del Panel (Audit Log) ]
```

### 2.1 Vista General (Metrics Overview Dashboard)
Orientado a gerentes operativos y de tecnología de tu cliente B2B. Muestra de forma gráfica la salud del canal de firma y métricas de consumo financiero.

*   **Tarjetas de KPIs Principales:**
    *   *Firmas Completadas:* Cantidad total de PDFs firmados exitosamente en el periodo seleccionado (con comparación porcentual con el mes anterior).
    *   *Eficiencia de Onboarding:* Tasa de conversión de usuarios (onboardings aprobados vs. abandonados/rechazados).
    *   *Latencia de TSA:* Tiempo promedio de respuesta del sellado de tiempo cualificado del PCSC de Paraguay (en milisegundos).
    *   *Consumo de Licencias:* Total de firmas consumidas frente al paquete contratado (ej. "8,450 / 10,000 firmas").
*   **Gráficos Visuales (Matplotlib / Plotly o componentes React):**
    *   *Tendencia Temporal:* Gráfico de líneas que muestra firmas completadas por día/semana.
    *   *Motivos de Rechazo en Onboarding:* Gráfico de dona (ej. "Fallo de Liveness: 45%", "Cédula borrosa: 35%", "AML/PEP flagged: 20%").
    *   *Distribución Geográfica:* Mapa de calor de Paraguay que representa los departamentos de origen de los firmantes mediante IPs.

### 2.2 Explorador de Transacciones (Transaction Explorer)
Una tabla dinámica avanzada de tipo data-table con soporte para filtrado masivo, ordenamiento y exportación de metadatos.

*   **Campos Visibles en Tabla:**
    *   `ID de Transacción` (UUIDv4 truncado para visualización).
    *   `Firmante` (Nombre y Apellido + Número de Cédula de Identidad).
    *   `Documento` (Nombre del archivo PDF original).
    *   `Fecha y Hora` (Sello de tiempo consolidado local PY: UTC-4 / UTC-3).
    *   `Biometría Score` (Porcentaje de coincidencia facial en formato semáforo: Verde $\ge 95\%$, Amarillo $90\%-94.9\%$, Rojo $<90\%$).
    *   `Estado` (Etiquetas: `INITIALIZED`, `ONBOARDING_APPROVED`, `COMPLETED`, `FAILED`, `REVOKED`).
*   **Controles de Filtrado y Búsqueda:**
    *   Búsqueda exacta por Cédula de Identidad (sin puntos) o Nombre.
    *   Rango de fechas transaccionales (filtro temporal).
    *   Filtro por estado de la firma o del onboarding.
    *   Filtro por score biométrico (ej. "Mostrar solo transacciones con coincidencia < 95%").

---

## 3. Visualizador Forense Detallado (Forensic Log Viewer)

Al hacer clic en cualquier transacción del *Explorador*, la interfaz despliega una vista detallada de pantalla completa dividida en pestañas lógicas. Esta vista es la **piedra angular para el perito informático forense**.

```
┌────────────────────────────────────────────────────────────────────────┐
│ DETALLE DE TRANSACCIÓN: UUID 9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d     │
├────────────────────────────────────────────────────────────────────────┤
│ [Pestaña 1: Identidad] [Pestaña 2: Red] [Pestaña 3: Consentimiento]    │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [Foto Cédula OCR]   ──► Match: 98.5% ◄──  [Selfie de Vida]           │
│  Nombre: Juan Pérez                                                    │
│  CI: 1.234.567                                                         │
│                                                                        │
│  [Datos de Red]                                                        │
│  IP: 190.104.128.5 (Tigo Paraguay)                                     │
│  Ubicación: Asunción, PY                                               │
│                                                                        │
│  [Evidencias de Consentimiento]                                        │
│  OTP WhatsApp: Enviado a +595981123456 (Entregado y Verificado)        │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Pestaña 1: Identidad y Onboarding Biométrico
Permite auditar el proceso de verificación de identidad del ciudadano paraguayo.

*   **Comparador Facial Uno-a-Uno (1:1):** Muestra lado a lado la selfie capturada en vivo por el usuario y la fotografía extraída mediante OCR del anverso de la Cédula de Identidad física paraguaya.
*   **Resultados de Verificaciones:**
    *   *Score de Coincidencia:* Indicador numérico (ej. "98.5%").
    *   *Prueba de Vida Activa (Liveness Detection):* Estado ("Aprobado" / "Score de confianza de movimiento").
    *   *Lectura OCR & MRZ:* Datos estructurados leídos del documento físico (Nombres, Apellidos, Sexo, Fecha de Nacimiento, Fecha de Vencimiento de Cédula).
    *   *Resultado AML/PEP:* Indicador de estatus de contraste contra bases de datos de lavado de activos y personas políticamente expuestas ("Limpio" / "No PEP" / "Sin coincidencias").

### 3.2 Pestaña 2: Conectividad y Logs Forenses de Red
Prueba el origen técnico del dispositivo utilizado por el firmante.

*   **Información del Dispositivo:**
    *   *Dirección IP Pública:* IPv4 o IPv6 desde la cual se realizó la transacción.
    *   *ISP (Proveedor de Internet):* Proveedor de telecomunicaciones paraguayo (ej. *Tigo, Personal, Copaco, Claro*).
    *   *Agente de Usuario (User-Agent):* Sistema operativo, navegador y versión exacta del dispositivo (ej. "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)...").
    *   *Geolocalización Estimada:* Coordenadas de latitud/longitud inferidas por IP e indicador geográfico en mapa interactivo incrustado (OpenStreetMap).

### 3.3 Pestaña 3: Consentimiento y Firma OTP
Prueba el acto deliberado de voluntad y posesión del número celular o cuenta de correo.

*   **Logs de OTP (One-Time Password):**
    *   *Canal utilizado:* Logotipo identificador (`WhatsApp` / `SMS` / `E-mail`).
    *   *Destino:* Teléfono en formato internacional E.164 (ej. `+595 981 123456`) o cuenta de correo electrónico enmascarada para privacidad.
    *   *Historial de Estado:* Timestamp de envío, timestamp de entrega (confirmación del Gateway de SMS/WhatsApp) y timestamp exacto en que el usuario ingresó el código en el frontend (con milisegundos).
    *   *Código Criptográfico:* Hash SHA-256 del código OTP utilizado, probando que no se almacenó el código original en texto plano por seguridad.

### 3.4 Pestaña 4: Integridad Criptográfica de Archivos
Permite verificar las huellas digitales únicas de los archivos procesados.

*   **Sección de Hashes Criptográficos:**
    *   *Hash del PDF Original:* Hash SHA-256 (ej. `e3b0c442...`) calculado al recibir el archivo desde el API B2B.
    *   *Hash del PDF Firmado:* Hash SHA-256 (ej. `a4f4944b...`) calculado tras inyectar incrementalmente el diccionario de firma PAdES-T.
*   **Detalles del Certificado del Firmante:**
    *   *Emisor (Issuer):* CA Intermedia del PSCNC.
    *   *Sujeto (Subject):* CN = Nombre del ciudadano, SerialNumber = Cédula.
    *   *Algoritmo:* `SHA256withRSA` o `ECDSA-SHA256`.
*   **Detalles del Sellado de Tiempo Cualificado (TSA):**
    *   *Autoridad de Tiempo:* Nombre del PCSC nacional que estampó la fecha cierta (ej. *Confirma S.A.*).
    *   *Número de Serie del Token TSA:* Identificador único provisto por el servidor de tiempo (RFC 3161).
    *   *Hora Oficial de la TSA:* Timestamp oficial de alta precisión.

---

## 4. Descarga Segura de Documentos y Evidencias

La visualización y descarga de archivos sensibles (el PDF firmado y el PDF consolidado de evidencias de la pista de auditoría) debe implementarse con el máximo estándar de seguridad de AWS para evitar la filtración de información confidencial.

```
                  [ FRONTEND: Dashboard React ]
                                │
                                │ 1. GET /v1/transactions/{id}/download-url
                                ▼
                   [ BACKEND: API Gateway ]
                                │
                                │ 2. Genera Pre-signed URL (Expiración: 5 min)
                                ▼
               [ STORAGE: Amazon S3 (Bucket Privado) ]
                                │
                                │ 3. Descarga directa temporal cifrada
                                ▼
                       [ CLIENTE B2B ]
```

### 4.1 Descargas Basadas en URLs Firmadas de AWS S3 (S3 Pre-signed URLs)
*   **Restricción de Acceso Público:** Los buckets de S3 que alojan documentos firmados y evidencias (`my-b2b-vault/signed/` y `my-b2b-vault/evidences/`) tienen desactivado el acceso público por completo de forma lógica y física (Block Public Access habilitado).
*   **Descarga Efímera:** Cuando el usuario del panel hace clic en "Descargar PDF Firmado" o "Descargar Reporte de Evidencias":
    1. El frontend realiza una llamada autenticada al API Gateway.
    2. El backend (AWS Lambda) valida los permisos de sesión e interactúa con el cliente S3 para generar una **Pre-signed URL** segura.
    3. Esta URL tiene una **validez temporal estricta de trescientos (300) segundos (5 minutos)**.
    4. El frontend redirige al navegador a la URL generada para la descarga directa y cifrada en tránsito (HTTPS) desde AWS S3.
    5. Transcurridos los 5 minutos, la URL queda automáticamente invalidada por AWS, previniendo accesos no autorizados posteriores.

---

## 5. Seguridad por Diseño en el Dashboard SaaS B2B

Dado que el panel administrativo maneja datos personales altamente sensibles de los firmantes (biometría y Cédula de Identidad), el frontend y su API de soporte deben incorporar salvaguardas avanzadas para mitigar el riesgo de fuga de información y espionaje corporativo.

### 5.1 Enmascaramiento Dinámico de Datos Personales (PII Masking)
Para cumplir con las mejores prácticas de privacidad y evitar la visualización masiva o no autorizada de datos de los firmantes:
*   **Cédula de Identidad:** Por defecto, los números de cédula se muestran parcialmente enmascarados en las tablas y vistas comunes (ej. `1.234.***`). Se requiere que el usuario haga clic sobre un icono de "Ojo" para revelar la información completa en caliente.
*   **Fotografías Sensibles (Selfie y CI):** Las miniaturas de las imágenes del documento y de la selfie del onboarding se muestran difuminadas mediante CSS (`filter: blur(8px)`) hasta que el usuario pase el cursor sobre ellas o haga clic para ampliarlas.
*   **Log de Revelación de Datos (PII Exposure Audit):** Cada vez que un usuario del panel revela un dato enmascarado (como el número de cédula completo o las imágenes de identidad), el backend dispara un evento automático que registra de forma inmutable quién, cuándo, por qué y sobre qué transacción se expuso información sensible en el panel.

### 5.2 Control de Acceso Basado en Roles (RBAC) y MFA Obligatorio
El sistema debe segregar estrictamente los accesos de los empleados de tus clientes B2B que inicien sesión en el portal:

| Rol de Usuario B2B | Permisos en el Dashboard | Tipo de Datos Visibles |
| :--- | :--- | :--- |
| **B2B_Super_Admin** | Gestión completa, creación de API Keys, configurar webhooks, visualización de métricas, auditoría. | Todos los campos (Enmascarados por defecto, revelación permitida). |
| **B2B_Legal_Auditor** | Búsqueda e inspección en el *Explorador de Transacciones*, visualización completa del *Folleto Forense* y descarga de reportes. | Acceso total para pericias informáticas forenses. |
| **B2B_Operator** | Inicializar transacciones, verificar estatus en tabla general, monitorear métricas operativas. | Solo datos parciales (Cédula de identidad y selfies enmascaradas sin permiso de revelación). |
| **B2B_Developer** | Configuración de credenciales de API, visualización de logs de error criptográfico y de comunicación. No puede ver transacciones ajenas al entorno de desarrollo. | Solo datos de prueba y entorno *Sandbox*. |

*   **Autenticación Multifactor (MFA) Mandatoria:** Para mitigar el riesgo de robo de credenciales corporativas, el inicio de sesión en el Panel SaaS (gestionado con **Amazon Cognito** o proveedores SAML/OIDC federados de tus clientes como Okta o Azure AD) requiere de forma obligatoria el uso de **MFA de un solo uso (TOTP)** provisto por aplicaciones de autenticación (Google Authenticator, Microsoft Authenticator).

### 5.3 Registro Inmutable de Logs de Acceso del Dashboard (Dashboard Access Audit)
Cualquier acción de consulta, búsqueda o descarga dentro de la interfaz administrativa se registra en tiempo real en una tabla dedicada de auditoría interna de accesos (`PSCNC_Dashboard_Audit_Log`):
*   Se captura el ID del usuario del panel, su IP de conexión, la acción realizada (`VIEW_TRANSACTION`, `REVEAL_PII`, `DOWNLOAD_EVIDENCE_PDF`) y la fecha y hora UTC.
*   Esta base de datos se guarda con la misma política de retención de dos (2) años y protección contra eliminación accidental (WORM S3 Object Lock) requerida por el marco de ciberseguridad del MITIC.

---

## 6. Prompt Estructurado para Claude AI (Generación de Código)

Copia y pega la siguiente instrucción en **Claude AI** para que diseñe y programe los componentes del Dashboard SaaS B2B basándose en esta especificación técnica:

```text
Escribe un componente completo de interfaz visual en React (usando TypeScript y Tailwind CSS) para la pestaña "Folleto Forense y Evidencias" de un Dashboard SaaS B2B de firma electrónica no cualificada (PSCNC) en Paraguay. 

El componente debe estructurarse de la siguiente manera:
1. Una sección superior que muestre el ID de Transacción (UUID), el nombre del firmante, su cédula, estado (COMPLETED) y un botón llamativo para "Descargar Expediente de Evidencias PDF" y otro para "Descargar PDF Firmado".
2. Una estructura de pestañas funcionales que contenga:
   - Pestaña "Identidad Biométrica": Comparador facial visual (selfie de vida vs. foto del CI, ambas difuminadas por defecto con un botón interactivo para "Revelar Datos PII" que registre la acción). Muestra también los campos extraídos del OCR de la cédula y el score de coincidencia biométrica (ej: 98.5% - Aprobado).
   - Pestaña "Logs de Conectividad": Tabla con la dirección IP pública, ISP paraguayo (ej. Tigo), User-Agent, y un mapa interactivo conceptual simulado de la geolocalización en Asunción.
   - Pestaña "Consentimiento y Firma": Detalle de envío de OTP por WhatsApp (número celular enmascarado), fecha de entrega, fecha de ingreso del código por el usuario y el hash SHA-256 del código OTP utilizado.
   - Pestaña "Criptografía e Integridad": Muestra los hashes SHA-256 del PDF original y firmado, datos del certificado X.509 de la CA subordinada emitido en AWS KMS y detalles del Token TSA cualificado de Paraguay (ej. Confirma S.A., RFC 3161).

Asegura que el diseño sea profesional, limpio (estilo Tailwind moderno con paleta oscura/clara, bordes redondeados y tipografía sans-serif) y simula de forma interactiva el comportamiento de enmascaramiento/difuminado de datos (blur) y el flujo de generación de URLs firmadas de AWS S3 mediante estados de React.
```
