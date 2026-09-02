# Especificación de Integración B2B: Flujo de APIs e Intercambio de Evidencias (Interseguros - Aseguradoras)

## 1. Introducción y Arquitectura de Integración
Este documento técnico detalla el flujo de integración de APIs y el intercambio seguro de evidencias forenses entre la plataforma de **Interseguros** (residente en AWS) y los sistemas **Core de las Compañías Aseguradoras** en Paraguay. 

Este diseño cumple estrictamente con el marco legal de la **Resolución SS.SG. N.º 210/2025** y la **Resolución SS.SG. N.º 231/2025** de la Superintendencia de Seguros (SIS), garantizando la validez de la propuesta mediante Firma Electrónica No Cualificada (FENC) y la posterior emisión de la póliza digital firmada con Firma Electrónica Cualificada (FEC) por parte de la aseguradora.

```
+──────────────────────────+                  +──────────────────────────+                  +──────────────────────────+
│       Interseguros       │                  │     Core Aseguradora     │                  │       PCSC Externo       │
│        (SaaS AWS)        │                  │     (Core de Seguros)    │                  │  (VIT, Confirma, etc.)   │
+─────────────┬────────────+                  +─────────────┬────────────+                  +─────────────┬────────────+
              │                                             │                                             │
              │ 1. Onboarding y Firma FENC (OTP)            │                                             │
              │────────────────────────────────────────────>│                                             │
              │                                             │                                             │
              │ 2. Envío de Propuesta + Folleto Forense     │                                             │
              │    (POST /v1/propuestas)                    │                                             │
              │────────────────────────────────────────────>│                                             │
              │                                             │ 3. Validación de Onboarding                 │
              │                                             │───────────────────────────┐                 │
              │                                             │                           │                 │
              │                                             │<──────────────────────────┘                 │
              │                                             │                                             │
              │                                             │ 4. Envío de Póliza a Firmar (FEC)           │
              │                                             │────────────────────────────────────────────>│
              │                                             │                                             │
              │                                             │ 5. Sello de Tiempo y Firma Cualificada      │
              │                                             │<────────────────────────────────────────────│
              │                                             │                                             │
              │ 6. Notificación Webhook Póliza Emitida      │                                             │
              │    (POST /webhooks/poliza-emitida)          │                                             │
              │<────────────────────────────────────────────│                                             │
              │                                             │                                             │
              │ 7. Despacho final al Cliente                │                                             │
              │────────────────────────────────────────────>│                                             │
              ▼                                             ▼                                             ▼
```

---

## 2. Secuencia Detallada de Procesamiento

### Paso 1: Onboarding y Consentimiento del Proponente (Interseguros)
1. El cliente inicia la compra de un seguro masivo en el portal o canal digital de Interseguros.
2. El sistema realiza el flujo completo de validación: OCR de Cédula, validación MRZ, Selfie-Match, prueba de vida (liveness) y contraste AML/PEP.
3. El cliente acepta la propuesta del seguro mediante un código de un solo uso (**OTP**) enviado por WhatsApp o SMS verificado.
4. El motor criptográfico de Interseguros genera un **Certificado Efímero** conforme a la Res. N.º 262/2024 del MIC e inyecta la firma incremental **PAdES** en el PDF de la Propuesta de Seguro.
5. De forma paralela, el sistema consolida el **Folleto Forense (Audit Trail)** en formato PDF, el cual es sellado criptográficamente con el Sello Electrónico Cualificado de Interseguros.

### Paso 2: Traspaso de la Propuesta y Evidencias al Core de la Aseguradora
Interseguros envía de manera síncrona la información comercial, el PDF de la propuesta firmada por el usuario y el PDF inmutable del Folleto Forense al endpoint de la aseguradora.

* **Endpoint en Aseguradora:** `POST /api/v1/propuestas`
* **Protocolo de Seguridad:** Mutual TLS (mTLS) forzado + Firma HMAC-SHA256 en cabecera para garantizar la autenticidad del Broker.

#### Ejemplo de Payload JSON (Request):
```json
{
  "transaccion_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "ramo_codigo": "MASIVO_VIDA_01",
  "broker_id": "INTERSEGUROS_PY",
  "cliente_datos": {
    "nombres": "Juan Pérez",
    "cedula_tipo": "PY_CI",
    "cedula_numero": "4567890",
    "telefono": "+595981123456",
    "correo": "juan.perez@email.py"
  },
  "propuesta_documento_b64": "JVBERi0xLjQKJ...[PDF_PROPUESTA_FIRMADO_CON_FENC]...",
  "folleto_forense_documento_b64": "JVBERi0xLjQKJ...[PDF_FOLLETO_FORENSE_CON_SELLO_EMPRESA]...",
  "metadatos_onboarding": {
    "onboarding_id": "onb_72189312",
    "biometric_score": 0.985,
    "ip_origen": "190.128.45.22",
    "timestamp_consentimiento": "2026-08-23T10:30:15Z",
    "otp_canal": "WHATSAPP",
    "otp_hash_sha256": "8a3e7db0d12e4f01ad428be52e92c234a413d9cf0120ab24f11e9f1a21e4cb8f"
  }
}
```

#### Respuesta de la Aseguradora (202 Accepted):
```json
{
  "propuesta_estado": "RECIBIDA_EN_ANALISIS",
  "aseguradora_transaccion_id": "asg_910283019283",
  "fecha_recepcion": "2026-08-23T10:30:18Z"
}
```

### Paso 3: Emisión de la Póliza Firmada con FEC (Aseguradora & PCSC)
1. El Core de la Aseguradora procesa y valida que el Folleto Forense esté correctamente sellado por Interseguros.
2. Al ser aprobado el riesgo, la aseguradora genera el documento de la **Póliza de Seguros**.
3. De conformidad con la **Resolución SS.SG. N.º 231/2025**, la aseguradora envía los bytes de la póliza a su módulo HSM conectado con su Prestador Cualificado de Servicios de Confianza (PCSC) local (ej. *Confirma, VIT S.A.*).
4. El PCSC estampa la **Firma Electrónica Cualificada (FEC)** del firmante autorizado de la aseguradora, junto con un **Sello de Tiempo Cualificado (TSA)** para otorgarle fecha cierta al documento (formato PAdES-T/LTA).

### Paso 4: Notificación por Webhook a Interseguros
La aseguradora notifica de forma asíncrona a Interseguros que la póliza ha sido formalmente emitida y adjunta el documento final firmado con validez legal plena.

* **Webhook en Interseguros (AWS):** `POST /webhooks/poliza-emitida`
* **Seguridad:** Verificación de firma criptográfica RSA de la aseguradora en los headers del webhook.

#### Ejemplo de Payload JSON (Webhook):
```json
{
  "transaccion_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "aseguradora_transaccion_id": "asg_910283019283",
  "poliza_numero": "POL-MAS-2026-102948",
  "poliza_estado": "EMITIDA_ACTIVA",
  "fecha_emision": "2026-08-23T10:32:00Z",
  "poliza_documento_url_firmada": "https://api.aseguradora.com.py/descargas/pol_102948.pdf?token=exp_300s_jwt...",
  "poliza_documento_b64": "JVBERi0xLjQKJ...[PDF_POLIZA_FIRMADO_CON_FEC]..."
}
```

---

## 3. Especificación de Seguridad de las Comunicaciones (AWS Context)

Para blindar el traspaso de datos sensibles de carácter biométrico y contractual, la arquitectura de Interseguros en AWS debe implementar el siguiente diseño de seguridad de red:

```
+─────────────────────────────── AWS VPC (Interseguros) ───────────────────────────────+
│                                                                                      │
│   +────────────────── Subred Pública (DMZ) ──────────────────+                      │
│   │                                                          │                      │
│   │   +───────────────────+             +────────────────+   │                      │
│   │   │   API Gateway     │────────────>│  AWS WAF       │   │                      │
│   │   │   (mTLS Enabled)  │             │  (OWASP Top10) │   │                      │
│   │   +───────────────────+             +────────────────+   │                      │
│   +──────────────────────────────────────────────────────────+                      │
│                                │                                                     │
│                                ▼                                                     │
│   +────────────────── Subred Privada (Segura) ───────────────+                      │
│   │                                                          │                      │
│   │   +───────────────────+             +────────────────+   │    +─────────────+   │
│   │   │   ECS / Fargate   │────────────>│  Amazon S3     │───┼───>│ S3 Glacier  │   │
│   │   │   (Signer Core)   │             │  (Bucket WORM) │   │    │ (Long Term) │   │
│   │   +───────────────────+             +────────────────+   │    +─────────────+   │
│   │             │                                            │                      │
│   │             ▼                                            │                      │
│   │   +───────────────────+                                  │                      │
│   │   │  Amazon DynamoDB  │                                  │                      │
│   │   │  (Audit Log)      │                                  │                      │
│   │   +───────────────────+                                  │                      │
│   +──────────────────────────────────────────────────────────+                      │
│                                                                                      │
+──────────────────────────────────────────────────────────────────────────────────────+
```

1. **Aislamiento de Tráfico:** El núcleo de firmado y almacenamiento reside en subredes privadas. Ningún componente con base de datos o almacenamiento de PDFs tiene acceso directo a Internet pública.
2. **Autenticación mTLS (Mutual TLS):** Se habilita mTLS en **AWS API Gateway** para las conexiones provenientes del Core de las Aseguradoras. Esto requiere configurar un Trust Store en S3 con los certificados de las CAs autorizadas de las compañías de seguros socias.
3. **Control Perimetral con AWS WAF:** Filtra cualquier petición maliciosa dirigida a los endpoints de webhooks, bloqueando accesos por geolocalización fuera de Paraguay (o zonas autorizadas) y limitando la tasa de peticiones para evitar ataques de denegación de servicio (DDoS).
4. **Cifrado Multi-Capas:**
   * **En tránsito:** Protocolo TLS 1.3 obligatorio.
   * **En reposo:** Cifrado con llaves gestionadas por el cliente (**SSE-KMS**) en DynamoDB y S3.
   * **WORM (Write Once, Read Many):** Activación de **S3 Object Lock** con retención de cumplimiento legal mínima de 2 años (para las pólizas y folletos de evidencias).

---

## 4. Prompt para Claude AI: Automatización del Componente de Integración

Copia y pega el siguiente prompt en Claude para generar el middleware o los controladores de integración listos para programar:

```text
Actúa como un Desarrollador Backend Senior especialista en Node.js/TypeScript y AWS. 
Basándote en la especificación del archivo de integración de Interseguros, genera:

1. Un controlador en NestJS para el endpoint del webhook `/webhooks/poliza-emitida` que reciba de forma segura la póliza firmada con FEC por parte de la aseguradora. El controlador debe:
   - Validar una firma HMAC en la cabecera (X-Interseguros-Signature) para verificar la autenticidad del payload enviado por la aseguradora.
   - Actualizar de forma atómica el estado de la transacción en Amazon DynamoDB (usando AWS SDK v3 @aws-sdk/client-dynamodb).
   - Descargar el binario del PDF de la póliza y guardarlo en un bucket de Amazon S3 con cifrado habilitado.
   - Desencadenar un evento interno para notificar al proponente vía AWS SNS o EventBridge.

2. Un cliente HTTP utilizando Axios que permita a Interseguros enviar la propuesta y el Folleto Forense al API de la aseguradora (`POST /api/v1/propuestas`), implementando políticas de reintento exponencial con jitter en caso de fallos de red (utilizando p-retry o similares).

Escribe código limpio, robusto, altamente tipado y listo para producción, siguiendo principios de Clean Architecture.
```
