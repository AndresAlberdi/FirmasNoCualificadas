# Especificación Técnica de Arquitectura: Sistema B2B de Firma Electrónica No Cualificada (FENC) en Paraguay

## 1. Introducción y Propósito
Este documento técnico está diseñado para ser consumido e interpretado por **Claude AI** u otros LLM avanzados de desarrollo con el fin de diseñar, estructurar y programar los módulos de un sistema SaaS B2B residente en AWS, enfocado en la generación de **Firmas Electrónicas No Cualificadas (FENC)** (firmas electrónicas simples) en la República del Paraguay. 

El sistema interactuará con un módulo de Onboarding digital existente (que ya realiza captura de Cédula de Identidad, OCR, validación MRZ, selfie, biometría facial, verificación de WhatsApp/correo, timestamp, IP y contraste AML/PEP). La meta principal es procesar un documento PDF recibido (el cual puede contar con firmas previas de otros certificados), inyectar criptográficamente la firma del usuario validado bajo el estándar internacional **PAdES** (PDF Advanced Electronic Signatures), obtener un Sello Cualificado de Tiempo de un Prestador de Servicios de Confianza nacional, y generar una Pista de Auditoría inmutable y sellada que sirva como blindaje legal ante tribunales paraguayos.

---

## 2. Alineación Legal y Regulatoria (República del Paraguay)

### 2.1 El Marco Normativo Vigente
*   **Ley N.º 6822/2021:** "De los Servicios de Confianza para las Transacciones Electrónicas, del Documento Electrónico y de los Documentos Transmisibles Electrónicos" (derogó la anterior Ley N.º 4017/2010 y su modificatoria, la Ley N.º 4610/2012). Alínea a Paraguay con el estándar europeo **eIDAS** y leyes modelo de la CNUDMI.
*   **Decreto Reglamentario N.º 7576/2022:** Establece los procedimientos de inicio de actividad y las directivas operativas de los Prestadores de Servicios de Confianza (PSC).
*   **Resolución N.º 262/2024 (MIC):** Aprueba el perfil del certificado del prestador no cualificado de servicios de confianza (documento de referencia `DOC-ICPP-20 Versión 2.0`).

### 2.2 Firma Electrónica Cualificada (FEC) vs. No Cualificada (FENC)
1.  **Firma Electrónica Cualificada (FEC):** Goza de presunción legal de autoría e integridad *iuris tantum* (Art. 40 y 43 de la Ley N.º 6822/2021). Si una de las partes la impugna, la carga de la prueba recae sobre el impugnante. Requiere obligatoriamente un certificado emitido por un Prestador Cualificado de Servicios de Confianza (PCSC) y un Dispositivo Cualificado de Creación de Firma (QSCD/DCCF).
2.  **Firma Electrónica No Cualificada (FENC / Firma Simple):** Goza de validez jurídica plena según el principio de no discriminación (Art. 39 de la Ley N.º 6822/2021). No obstante, **carece de presunción legal automática de autoría**. Si el firmante la desconoce en sede civil (Art. 308 del Código Procesal Civil), la carga de la prueba se invierte. El emisor/plataforma debe demostrar mediante una **pericia informática forense** que la firma fue realizada por el firmante bajo su control exclusivo y que el documento no fue alterado con posterioridad.

### 2.3 Constitución como Prestador de Servicios de Confianza No Cualificado (PSCNC)
Para que el sistema B2B tenga validez regulatoria plena e interoperabilidad frente a auditorías del Ministerio de Industria y Comercio (MIC), la persona jurídica que explote el SaaS debe realizar el siguiente trámite administrativo:
*   **Plazo de Notificación:** Presentar la comunicación formal ante la Dirección General de Firma Digital y Comercio Electrónico (DGFDCE) del MIC dentro de los **tres (3) meses** contados a partir del inicio efectivo de la operación (Art. 15 de la Ley N.º 6822/2021 y Art. 5 del Decreto N.º 7576/2022).
*   **Requisito de Registro (REPSE):** Estar previamente inscrito de forma gratuita en el **Registro de Prestadores de Servicios (REPSE)** a través de la ventanilla única de importación/comercio del MIC (conforme al Decreto N.º 6866/2011).
*   **Documentación obligatoria a presentar (vía info-dgce@mic.gov.py):**
    1.  Formulario oficial de comunicación técnica.
    2.  **Declaración de Prácticas de los Servicios de Confianza (DPSC):** Documento formal detallando la infraestructura, algoritmos criptográficos utilizados, resguardo de datos y procesos de onboarding.
    3.  Ajuste del perfil de certificados al estándar nacional `DOC-ICPP-20` (Resolución N.º 262/2024).

---

## 3. Arquitectura Tecnológica en AWS (Security by Design)

El sistema B2B debe estructurarse bajo un modelo de arquitectura de microservicios sin servidor (serverless) o contenerizado (ECS/Fargate) para asegurar escalabilidad y aislamiento de datos de inquilinos (B2B Multi-tenant).

```
                      [ Client B2B APP ]
                              │ (HTTPS / mTLS)
                              ▼
                       [ AWS WAF ]
                              │
                              ▼
                     [ API Gateway ]
                              │
             ┌────────────────┴────────────────┐
             ▼                                 ▼
   [ Auth / Cognito ]                [ ECS / Fargate Signer ]
                                               │
                                 ┌─────────────┼──────────────┐
                                 ▼             ▼              ▼
                           [ AWS KMS ]   [ DynamoDB ]   [ S3 Glacier ]
                          (CA Privada)   (Evidencias)    (Auditoría)
```

### 3.1 Infraestructura Criptográfica y Administración de Claves (AWS KMS)
*   **Entidad de Certificación Interna (Intermediate CA):** El sistema actuará como una CA subordinada para emitir certificados X.509 de corto ciclo de vida (Short-Lived Certificates) para los firmantes en cada transacción. La clave privada de esta Intermediate CA se creará y resguardará de forma exclusiva en **AWS KMS (Key Management Service)** utilizando llaves asimétricas RSA de 2048 o 4096 bits (o curvas elípticas ECDSA P-256) respaldadas por hardware criptográfico FIPS 140-2 Nivel 3.
*   **Aislamiento Criptográfico:** Nunca se extraerá la clave privada de la CA intermedia fuera de KMS. Las operaciones de firma de certificados efímeros de los usuarios se realizarán a través de la llamada al API de KMS `Sign`.

### 3.2 Seguridad de API e Integración B2B
*   **Autenticación B2B:** Uso de **mTLS (mutual TLS)** en AWS API Gateway para asegurar la comunicación directa con los servidores de los clientes B2B, o en su defecto, autenticación mediante **API Keys rotativas** custodiadas en **AWS Secrets Manager** y firmas de petición basadas en **HMAC-SHA256**.
*   **Seguridad Perimetral:** Despliegue de **AWS WAF** (Web Application Firewall) frente al API Gateway con reglas OWASP Top 10 y limitación de tasa (Rate Limiting) por cliente.
*   **Protección de Datos en Tránsito y Reposo:** Cifrado TLS 1.3 forzado en tránsito. Cifrado AES-256 (SSE-KMS) en reposo para bases de datos (Amazon DynamoDB/RDS) y repositorios de documentos (Amazon S3).

---

## 4. Ingeniería de Firma en PDFs: Estándar PAdES y Evidencias

La firma de un PDF recibido como input debe realizarse de forma secuencial e incremental para no corromper ni invalidar firmas previas (estén o no basadas en certificados cualificados).

### 4.1 Ciclo de Vida del Firmado Incremental en PDF (PAdES)
1.  **Cálculo de Hash Unitario:** El microservicio de firma lee el PDF original y calcula el hash criptográfico SHA-256 del rango de bytes del documento, excluyendo el espacio preasignado para el bloque de firma (`/ByteRange`).
2.  **Generación de Certificado Efímero (Short-Lived Certificate):** Tras confirmarse el onboarding, el sistema genera dinámicamente un par de claves públicas/privadas de un solo uso para el firmante. Emite un certificado X.509 firmado por la Intermediate CA del PSCNC que contiene:
    *   `CN` (Common Name): Nombre completo del firmante.
    *   `SerialNumber`: Número de Cédula de Identidad de Paraguay.
    *   `OU` (Organizational Unit): "Firma Electrónica No Cualificada - Transacción [ID]".
    *   `Validity`: Inicio en `T-5 min` y fin en `T+1 hora` (evita ventanas de riesgo por robo de identidad posterior).
3.  **Inyección Criptográfica:** El módulo genera el bloque de firma en formato PKCS#7 / CMS (Cryptographic Message Syntax) utilizando la clave privada efímera del usuario y el certificado temporal. Se inyecta incrementalmente al final del archivo PDF.
4.  **Actualización Incremental del PDF:** La especificación PAdES requiere que los cambios se agreguen al final del archivo binario sin reescribir los offsets originales del PDF. El nuevo diccionario de firma `/Sig` se asocia lógicamente a un `/Annot` visible o invisible en el documento.

### 4.2 Integración del Sello Cualificado de Tiempo (PAdES-T)
Para otorgar **fecha cierta** incontestable y cumplir con el artículo 56 de la Ley N.º 6822/2021, la firma debe escalarse al nivel **PAdES-T (Timestamp)**:
*   **Consumo de TSA Cualificado:** El sistema emite una petición de sellado de tiempo basada en el estándar **RFC 3161 (TSP)** al servidor de una Autoridad de Sellado de Tiempo (TSA) operada por un Prestador Cualificado de Servicios de Confianza (PCSC) formalmente autorizado en Paraguay (ej. *Confirma, VIT S.A., CODE 100, Documenta o SOS Tecnología*).
*   **Estructura de la Petición:** Se envía el hash del diccionario de firma recién creado. El PCSC responde con un token de tiempo firmado por su clave privada de alta seguridad vinculada a la AC Raíz del Paraguay.
*   **Inyección del Token TSA:** Este token se incrusta dentro del atributo no firmado `signature-time-stamp` del bloque PKCS#7 de la firma en el PDF.

### 4.3 Validación a Largo Plazo (PAdES-B-LTA)
Para contratos de alta duración, se recomienda el nivel **PAdES-B-LTA**:
*   **Incrustación LTV (Long Term Validation):** El sistema recopila la cadena completa de certificados de validación, junto con las respuestas **OCSP** (Online Certificate Status Protocol) o las listas de revocación de certificados (**CRL**) del emisor de la CA del PSCNC en el instante de la firma.
*   **Inyección en `/DSS`:** Estos metadatos se graban en el diccionario de soporte de seguridad del documento (`/DSS`), permitiendo que lectores estándar (como Adobe Acrobat) validen la firma años después de que los certificados hayan expirado o hayan sido modificados, sin necesidad de conexión a internet.

---

## 5. La Pista de Auditoría Inmutable (Documento de Evidencias)

Ante un escenario de desconocimiento judicial, la única defensa del emisor es la **Pista de Auditoría** (*Audit Trail*), la cual se consolida en un archivo PDF independiente de evidencias técnicas.

### 5.1 Campos Estructurados del Microservicio de Auditoría
Para cada sesión de firma, el microservicio debe capturar y registrar en una base de datos relacional o Key-Value (DynamoDB) los siguientes elementos con estricta integridad referencial:

| Campo / Evidencia | Tipo de Dato | Origen / Método de Captura | Propósito en Pericia Forense |
| :--- | :--- | :--- | :--- |
| **Transaction_ID** | UUIDv4 | Autogenerado por el backend. | Identificador único de la sesión de onboarding y firma. |
| **Document_Hash_Original** | Hex String (SHA-256) | Calculado del binario del PDF antes de cualquier firma. | Probar que el documento original no fue modificado de origen. |
| **Document_Hash_Signed** | Hex String (SHA-256) | Calculado del binario final tras inyectar la firma PAdES. | Garantizar la integridad criptográfica posterior al acto de firmar. |
| **User_Identity_Metadata** | JSON | Datos estructurados del Onboarding (Cédula de Identidad, nombres, OCR MRZ, Selfie-Match score). | Vincular unívocamente la firma a una persona física real verificada. |
| **Network_Evidence** | JSON | IP pública del dispositivo del firmante (`X-Forwarded-For`), puerto y cabecera `User-Agent`. | Evidencia forense de conexión física y tipo de dispositivo utilizado. |
| **SMS/WhatsApp_OTP_Log** | JSON | ID de transacción de mensajería, número celular destino (formato E.164), timestamp de envío y confirmación del código de 6 dígitos. | Demostrar factor de posesión del teléfono móvil y voluntad del firmante. |
| **Timestamp_RFC_3161** | DateTime | Sello de tiempo obtenido de la TSA cualificada de Paraguay. | Garantía legal de hora cierta oficial. |

### 5.2 Sellado Criptográfico del Expediente de Evidencias
Una vez que el documento de evidencias (PDF consolidado con la pista de auditoría y capturas visuales del CI/Selfie) es generado:
1.  Se aplica un **Sello Electrónico Cualificado** de la plataforma (adquirido mediante un certificado de persona jurídica emitido por un PCSC calificado en Paraguay).
2.  La clave privada de este sello corporativo reside en un HSM corporativo. Esto evita de manera absoluta la alteración del expediente de evidencias por parte de desarrolladores, administradores de base de datos o atacantes, proveyendo valor probatorio autónomo bajo el Art. 63 de la Ley N.º 6822/2021.

---

## 6. Arquitectura Multiagente de Implementación y Orquestación

Para guiar el diseño del código fuente, el diseño del sistema debe ser orquestado por un modelo de **Sistemas Multiagente**. Claude AI debe instanciar y estructurar el desarrollo mediante los siguientes perfiles de agentes lógicos:

```
              ┌───────────────────────────────────────┐
              │          Agente Coordinador           │
              └──────────────────┬────────────────────┘
                                 │
         ┌───────────────────────┼───────────────────────┐
         ▼                       ▼                       ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Agente Legal   │     │  Agente Cripto  │     │ Agente Auditor  │
│  y Cumplimiento │     │   de Firmado    │     │   y Evidencias  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

### Agent 1: Agente de Coordinación y Control (Orchestrator Agent)
*   **Responsabilidad:** Administrar la máquina de estados de la transacción de firma. Recibir las llamadas del API B2B, coordinar las llamadas cruzadas entre agentes y responder al cliente.
*   **Lógica:** Asegurar que ningún documento se envíe a firmar si el estado del onboarding en la base de datos no es `APPROVED` con coincidencia biométrica > 95%.

### Agent 2: Agente Legal y de Cumplimiento de Políticas (Regulatory Agent)
*   **Responsabilidad:** Validar las restricciones de uso del documento y el perfil de los certificados X.509 generados efímeramente.
*   **Lógica:** Analizar el tipo de transacción mediante técnicas de clasificación de texto o metadatos del PDF. Si detecta palabras clave como "hipoteca", "donación", "testamento" o "matrimonio", bloquear el proceso de firma electrónica no cualificada y lanzar una excepción HTTP 403 (restricción por exclusión legal según Ley N.º 6822/2021). Asegurar que los OIDs y atributos del certificado cumplan rigurosamente con la norma `DOC-ICPP-20` de la DGFDCE.

### Agent 3: Agente Criptográfico de Firmado e Integridad (Crypto Engine Agent)
*   **Responsabilidad:** Realizar las operaciones matemáticas y la estructuración del binario PDF bajo el estándar PAdES.
*   **Lógica:** Extraer los bytes del PDF, gestionar las firmas secuenciales/incrementales, programar la llamada a AWS KMS para generar el bloque PKCS#7 y realizar el formateo ASN.1 correspondiente.

### Agent 4: Agente de Auditoría, Sellado de Tiempo y Alertas (Security & TSA Agent)
*   **Responsabilidad:** Interactuar con servicios externos (TSA cualificadas de Paraguay) y consolidar el expediente inmutable de evidencias.
*   **Lógica:** Gestionar llamadas HTTP asíncronas con reintentos exponenciales hacia los endpoints de los PCSC locales. Consolidar el JSON y PDF del "Audit Trail", mandar a llamar al HSM corporativo para estampar el Sello Electrónico de Confianza, y disparar alertas inmediatas vía AWS SNS a los ingenieros de SecOps si se detecta un fallo de verificación de firma o discrepancia de geolocalización.

---

## 7. Especificación de APIs del Módulo de Firma

### 7.1 `POST /v1/signing-sessions`
Inicializa un proceso de firmado B2B vinculando el Onboarding previo y cargando el documento original.

**Request Header:**
```http
Authorization: Bearer <B2B_JWT_Token_or_HMAC>
Content-Type: multipart/form-data
```

**Request Body (form-data):**
*   `onboarding_token` (String, Obligatorio): Token único que referencia el onboarding aprobado del usuario en el otro módulo.
*   `pdf_document` (File, Obligatorio): Archivo PDF a firmar (puede contener firmas previas).
*   `metadata` (JSON String, Opcional): Información transaccional del cliente B2B.

**Response (201 Created):**
```json
{
  "signing_session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "INITIALIZED",
  "original_document_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "created_at": "2026-08-22T21:43:23Z",
  "expires_at": "2026-08-22T22:43:23Z"
}
```

### 7.2 `POST /v1/signing-sessions/{id}/confirm`
Ejecuta de manera atómica el firmado incremental PAdES-T, integrando la firma del usuario con el sello cualificado de tiempo y validando el consentimiento activo mediante OTP.

**Request Body:**
```json
{
  "consent_otp_code": "481926",
  "signature_coordinate_x": 100,
  "signature_coordinate_y": 150,
  "signature_page": 1,
  "visual_signature_enabled": true
}
```

**Response (200 OK):**
```json
{
  "signing_session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "COMPLETED",
  "signed_document_hash": "a4f4944be6fc3a1599bf461c9e6fa91418be21e46422b934ca495991b782c918",
  "timestamp_authority": "CONFIRMA S.A.",
  "timestamp_serial": "841295832",
  "timestamp_time": "2026-08-22T21:43:35Z"
}
```

### 7.3 `GET /v1/signing-sessions/{id}/evidence`
Permite descargar tanto el documento firmado como el expediente completo de evidencias (Audit Trail) sellado criptográficamente.

**Response (200 OK):**
```json
{
  "signing_session_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "COMPLETED",
  "signed_document_url": "https://s3.us-east-1.amazonaws.com/my-b2b-vault/signed/9b1deb4d.pdf",
  "evidence_report_url": "https://s3.us-east-1.amazonaws.com/my-b2b-vault/evidences/9b1deb4d_evidence.pdf",
  "verifications": {
    "aml_pep_checked": true,
    "biometric_score": 0.985,
    "identity_match_approved": true
  }
}
```

---

## 8. Procedimientos Operativos Críticos

### 8.1 Políticas de Control de Revocación e Infracciones
Como Prestador No Cualificado (PSCNC) de confianza, el sistema debe administrar la trazabilidad y ciclo de vida de su clave de CA intermedia:
*   **Revocación de CA Intermedia:** En caso de sospecha de compromiso de la clave privada de la CA residente en AWS KMS, se debe generar un evento de revocación inmediato. El sistema debe publicar un servicio de lista de certificados revocados (**CRL**) de la plataforma en un endpoint HTTPS público registrado en la Declaración de Prácticas de los Servicios de Confianza.
*   **Revocación de Firmas de Usuario:** Dado que los certificados de firma emitidos a los usuarios son efímeros (vigencia de minutos para firmar una sola transacción), la revocación no aplica en caliente para el usuario individual, sino que se previene suspendiendo temporalmente el acceso del firmante en el módulo de onboarding. En caso de reportarse robo de identidad, se marca la sesión de firma en la base de datos como `COMPROMISED` y se actualiza el estatus del expediente de evidencias.

### 8.2 Monitoreo de Seguridad de Información y Reportes de Incidentes
*   **Monitoreo Continuo:** Implementación de logs estructurados con **AWS CloudTrail** y **Amazon CloudWatch**, con alarmas configuradas para detectar llamadas API fallidas de KMS o accesos no autorizados a las bases de datos de evidencias.
*   **Plazo Legal de Reporte de Incidentes:** Conforme al Artículo 6 del Decreto N.º 7576/2022 y regulaciones del MITIC/CERT-Py, el sistema debe contar con un plan automático de respuesta a incidentes de SecOps que asegure la notificación al correo oficial de la DGFDCE del MIC en un plazo **máximo improrrogable de veinticuatro (24) horas** en caso de intrusiones, incidentes de denegación de servicio (DDoS) exitosos o sospechas de alteración de base de datos.
*   **Políticas de Retención de Datos:** La información del onboarding, de las pistas de auditoría y los documentos procesados deben almacenarse y custodiar bajo estrictas políticas de retención de datos por un período mínimo de **dos (2) años** contados a partir de la finalización de los efectos legales del documento firmado, utilizando clases de almacenamiento con protección WORM (Write Once, Read Many) como **Amazon S3 Object Lock** en modo "Compliance" para impedir borrados accidentales o intencionados.

## 9. Anexo: Ruta de Cumplimiento Administrativo y Formalización ante el MIC

Este anexo detalla la ruta crítica de trámites, plazos, ventanillas y requisitos técnicos obligatorios que la persona jurídica explotadora del SaaS de Firma Electrónica No Cualificada (FENC) debe ejecutar para operar de forma 100% regular ante el Ministerio de Industria y Comercio (MIC) y la DGFDCE [28, 295].

```
                     [ Inicio Operativo Técnico en AWS ]
                                     │
                                     ▼
                [ Registro en REPSE - Portal VUE (48hs) ]
                                     │
                                     ▼
                [ Inicio Efectivo de Servicios FENC B2B ]
                                     │
                                     ▼ (Plazo Máx: 3 Meses)
               [ Notificación de Inicio a DGFDCE (MIC) ]
               ┌─────────────────────┴─────────────────────┐
               ▼                                           ▼
 [ Declaración de Prácticas (DPSC) ]         [ Perfil de Certificados X.509 ]
 (Políticas de Ciberseguridad/Evidencias)    (Ajuste Estándar Res. 262/2024)
                                     │
                                     ▼
                  [ Publicación en Listado de PSCNC ]
```

### 9.1 Paso 1: Inscripción Obligatoria en el Registro de Prestadores de Servicios (REPSE)

Antes de realizar la comunicación formal como prestador de servicios de confianza no cualificado (PSCNC), la empresa constituida bajo leyes paraguayas (S.A., S.R.L. o EAS) debe estar inscrita de manera obligatoria y gratuita en el Registro de Prestadores de Servicios (REPSE) [281, 296].

*   **Fundamento Legal:** Decreto N.º 6866/2011 y Resolución N.º 1260/2016 del MIC [292].
*   **Ventanilla de Tramitación:** Portal de la Ventanilla Única de Exportación (VUE) en **`www.vue.org.py`** [281, 297].
*   **Modalidad de Trámite:** 100% electrónico y en línea [303].
*   **Costo:** Sin costo (Gratuito) [303].
*   **Tiempo de Resolución (SLA):** 48 horas hábiles tras el envío de la solicitud [303].
*   **Requisitos Documentales para Personas Jurídicas (SaaS B2B):**
    1.  Copia de la **Constancia de RUC** activo en estado "ACTIVO" [216, 285].
    2.  Copia de la **Cédula de Identidad** vigente de los directores o representantes legales (para extranjeros: carnet de admisión temporal o permanente) [285].
    3.  Copia de la **Escritura de Constitución de la Sociedad** registrada e inscripta en el registro correspondiente (EAS, S.A., S.R.L.), incluyendo en el objeto social actividades relacionadas con tecnología de la información o servicios de software [4, 285].
    4.  Copia del **Acta de la Última Asamblea** (para Sociedades Anónimas) [4].
    5.  Copia de la **Patente Comercial / Profesional** municipal vigente [285].
    6.  Copia de la factura comercial o planilla del IPS vigente (en caso de contar con empleados registrados) [285].
    7.  *Responsable Técnico:* De requerirse un responsable técnico por el tipo de actividad, adjuntar copia de su cédula, título universitario o matrícula profesional y el contrato que lo vincula legalmente con la sociedad (el técnico también debe estar registrado en el REPSE) [286].

### 9.2 Paso 2: Notificación Formal de Inicio de Actividades ante la DGFDCE

Al no requerir autorización previa del MIC para iniciar operaciones como PSCNC, la ley paraguaya concede libertad de inicio operativo, pero impone un estricto deber de comunicación posterior [84, 275].

*   **Fundamento Legal:** Artículo 15 de la Ley N.º 6822/2021 [84, 295] y Artículo 5 del Decreto Reglamentario N.º 7576/2022 [31, 295].
*   **Plazo Legal Improrrogable:** Dentro de un plazo de **tres (3) meses** contados a partir del inicio efectivo de la prestación comercial del servicio de firmas [31, 84, 298]. La omisión o el retraso en este plazo constituye una infracción sujeta a sumario administrativo y multas económicas de acuerdo al régimen sancionador del MIC [2, 298].
*   **Ventanilla de Entrega:** Envío de manera electrónica al correo institucional oficial de la Dirección General de Firma Digital y Comercio Electrónico: **`info-dgce@mic.gov.py`** [5, 222, 298].
*   **Documentación Técnica Específica a Entregar:**
    1.  **Formulario Oficial de Solicitud:** Completar y firmar digitalmente el formulario equivalente (similar a los perfiles FOR-ICPP-07/FOR-ICPP-05 adaptados para el sector no cualificado) [5, 222, 298].
    2.  **Declaración de Prácticas de los Servicios de Confianza (DPSC):** Documento normativo formal donde se detallan los algoritmos criptográficos del motor (AWS KMS, SHA-256), las medidas de seguridad perimetral (AWS WAF, API Gateway con mTLS), los flujos del Onboarding biométrico (verificación de identidad facial) y la preservación inmutable del expediente de evidencias técnicas (S3 Object Lock Compliance Mode) [6, 9, 298].
    3.  **Certificado de Adecuación a la Resolución N.º 262/2024:** El PSCNC debe demostrar técnicamente que la estructura y plantillas de los certificados electrónicos temporales (Short-Lived Certificates) generados por su CA intermedia en AWS KMS cumplen rigurosamente con los formatos obligatorios establecidos por el MIC en la **Resolución N.º 262/2024** (la cual aprueba el perfil del certificado del prestador no cualificado de servicios de confianza, identificado como `DOC-ICPP-20 Versión 2.0`) [29, 298].

### 9.3 Paso 3: Cumplimiento de Obligaciones Operativas y Ciberseguridad (Post-Registro)

Una vez incluido el SaaS en el Listado Público de Prestadores de Servicios de Confianza No Cualificados en la web oficial del MIC (`www.acraiz.gov.py`) [31, 295], operan las siguientes exigencias de fiscalización y gobernanza informática:

*   **Notificación de Incidentes de Seguridad en 24 Horas:** Conforme al Artículo 6 del Decreto N.º 7576/2022 y la Resolución N.º 1385/2022, ante cualquier incidente que afecte significativamente la confidencialidad, disponibilidad o integridad de las firmas o de los datos personales (ej: ataques DDoS exitosos, filtración de evidencias de onboarding, quiebre lógico de llaves), el PSCNC debe notificar formalmente de manera electrónica en un **plazo máximo de 24 horas** a la DGFDCE (`info-dgce@mic.gov.py`) y al Centro de Respuestas a Incidentes Cibernéticos del MITIC (**CERT-Py**) [32, 48, 299].
*   **Tratamiento de Datos de Onboarding (Biometría y Selfie):** Los datos recolectados durante la identificación de la persona (fotos de la cédula, OCR, biometría facial, logs de OTP de WhatsApp) se consideran datos estrictamente transaccionales con consentimiento expreso del firmante [2, 299]. Se prohíbe su uso para fines comerciales de minería de datos y deben conservarse por un plazo mínimo de **dos (2) años** contados a partir del vencimiento de los efectos jurídicos del documento firmado (o según plazos específicos sectoriales, como los 2 años exigidos por la Superintendencia de Seguros en pólizas electrónicas bajo la Res. SS.SG. N.º 210/2025) [241, 299].
*   **Auditorías Técnicas de Vulnerabilidad:** En alineación con las Resoluciones del MITIC N.º 277/2020 (Controles Críticos de Ciberseguridad) [253] y N.º 553/2024 (Lineamientos de Gobierno Electrónico) [252], el prestador debe aplicar análisis continuos de vulnerabilidades ("Penetration Testing") sobre sus API, infraestructura de Kubernetes (EKS/Fargate) y bases de datos en AWS antes de desplegar actualizaciones críticas del software a producción [255, 311].
