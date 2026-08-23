# Especificación Técnica de Base de Datos: Pista de Auditoría Forense (Audit Trail) para PSCNC en Paraguay

Este documento define la estructura de datos exacta para la base de datos de auditoría de un **Prestador de Servicios de Confianza No Cualificados (PSCNC)** en Paraguay. Está diseñado específicamente para que **Claude AI** u otros sistemas de desarrollo automatizado puedan interpretarlo y generar directamente esquemas de base de datos NoSQL, modelos de validación en lenguajes como Python/TypeScript (Pydantic/Zod) o scripts de despliegue de infraestructura en AWS.

La base de datos de auditoría, denominada `PSCNC_Audit_Trail` en **Amazon DynamoDB**, es la pieza central que garantiza la **validez jurídica** de las Firmas Electrónicas No Cualificadas (FENC) en sede judicial bajo la **Ley N.º 6822/2021** de Paraguay. Proporciona la evidencia inmutable necesaria para superar una **pericia informática forense** en caso de que un firmante pretenda desconocer su firma (Art. 39 y 40 de la Ley, en relación con la inversión de la carga de la prueba).

---

## 1. Modelo de Datos y Diseño de Llaves en Amazon DynamoDB

Para optimizar el costo, asegurar la escalabilidad horizontal infinita y permitir consultas forenses rápidas, se implementa un diseño de **Tabla Única (Single-Table Design)** en Amazon DynamoDB.

### 1.1 Estructura de la Tabla: `PSCNC_Audit_Trail`

*   **Capacidad de Lectura/Escritura:** On-Demand (PAYG - Pay-As-You-Go) para manejar picos transaccionales B2B sin aprovisionamiento previo.
*   **Cifrado en Reposo:** Activado por defecto utilizando claves administradas por el cliente en **AWS KMS** (`aws/dynamodb`).
*   **Protección WORM (Write-Once-Read-Many):** Integrado con DynamoDB Streams para replicar eventos a un bucket de Amazon S3 protegido con **S3 Object Lock** en modo "Compliance" (retención mínima de 2 años obligatorios según el MITIC).

### 1.2 Atributos Clave y Global Secondary Indexes (GSIs)

| Atributo / Índice | Rol Criptográfico / Operativo | Tipo | Formato de Valor / Ejemplo | Propósito Forense |
| :--- | :--- | :--- | :--- | :--- |
| **PK** | Partition Key Principal | String | `TX#[Transaction_ID]` <br> *Ej: `TX#c09e3e3b-57fc-47e0-91bf-a9f8365ef5cb`* | Aislamiento y acceso directo y atómico a una sesión de firma individual. |
| **SK** | Sort Key Principal | String | `METADATA#V1` | Permite el versionamiento del expediente si hay firmas subsecuentes o reintentos. |
| **GSI1PK** | Partition Key GSI 1 | String | `CI#PY-[Nro_Cedula]` <br> *Ej: `CI#PY-4829153`* | Permite realizar búsquedas indexadas y correlacionar todas las transacciones de un ciudadano. |
| **GSI1SK** | Sort Key GSI 1 | String | `TIMESTAMP` <br> *Ej: `2026-08-23T04:57:00Z`* | Ordenamiento cronológico de las firmas realizadas por una persona física. |
| **GSI2PK** | Partition Key GSI 2 | String | `CLIENT#[B2B_Client_ID]` <br> *Ej: `CLIENT#bancosud-prod`* | Permite aislar y reportar logs transaccionales para cobros o auditorías de clientes B2B. |
| **GSI2SK** | Sort Key GSI 2 | String | `TIMESTAMP` | Ordenamiento temporal para reportes consolidados por cliente B2B. |

---

## 2. Esquema JSON Completo (Audit Trail Document Schema)

Cada registro almacenado bajo la llave `TX#[Transaction_ID]` contiene un documento JSON enriquecido y estructurado que captura los cuatro pilares fundamentales de la pericia de firma electrónica simple: **Identidad (Quién), Voluntad (Cómo), Red/Entorno (Dónde) y Documento (Qué)**.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "PSCNC_Audit_Trail_Item",
  "type": "object",
  "required": [
    "PK",
    "SK",
    "transaction_id",
    "b2b_client_id",
    "status",
    "created_at",
    "completed_at",
    "identity_evidence",
    "network_evidence",
    "consent_evidence",
    "cryptographic_evidence"
  ],
  "properties": {
    "PK": {
      "type": "string",
      "pattern": "^TX#[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$"
    },
    "SK": {
      "type": "string",
      "pattern": "^METADATA#V[0-9]+$"
    },
    "GSI1PK": {
      "type": "string",
      "pattern": "^CI#PY-[0-9]+$"
    },
    "GSI1SK": {
      "type": "string",
      "format": "date-time"
    },
    "GSI2PK": {
      "type": "string",
      "pattern": "^CLIENT#[a-zA-Z0-9_.-]+$"
    },
    "GSI2SK": {
      "type": "string",
      "format": "date-time"
    },
    "transaction_id": {
      "type": "string",
      "format": "uuid"
    },
    "b2b_client_id": {
      "type": "string"
    },
    "status": {
      "type": "string",
      "enum": ["INITIALIZED", "ONBOARDING_COMPLETED", "SIGNING_COMPLETED", "FAILED", "REVOKED", "COMPROMISED"]
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "completed_at": {
      "type": "string",
      "format": "date-time"
    },
    "identity_evidence": {
      "type": "object",
      "required": [
        "document_type",
        "national_id",
        "first_name",
        "last_name",
        "birth_date",
        "ocr_mrz_raw",
        "ocr_confidence",
        "facial_match_score",
        "liveness_detected",
        "verification_partner_id"
      ],
      "properties": {
        "document_type": {
          "type": "string",
          "enum": ["CI_PY", "PASAPORTE"]
        },
        "national_id": {
          "type": "string",
          "pattern": "^[0-9]+$"
        },
        "first_name": { "type": "string" },
        "last_name": { "type": "string" },
        "birth_date": {
          "type": "string",
          "format": "date"
        },
        "ocr_mrz_raw": {
          "type": "string",
          "description": "Texto crudo de la Zona de Lectura Mecánica (MRZ) del reverso de la cédula paraguaya."
        },
        "ocr_confidence": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0
        },
        "facial_match_score": {
          "type": "number",
          "minimum": 0.0,
          "maximum": 1.0,
          "description": "Porcentaje de coincidencia entre la selfie del onboarding y la foto extraída de la cédula o padrón oficial."
        },
        "liveness_detected": {
          "type": "boolean",
          "description": "Prueba activa de vida (Liveness Detection) para mitigar suplantaciones por fotos o videos."
        },
        "liveness_meta": {
          "type": "object",
          "properties": {
            "liveness_vendor": { "type": "string" },
            "liveness_confidence": { "type": "number" },
            "spoof_check_passed": { "type": "boolean" }
          }
        },
        "verification_partner_id": {
          "type": "string",
          "description": "ID de auditoría del sistema de validación del proveedor externo de biometría."
        }
      }
    },
    "network_evidence": {
      "type": "object",
      "required": [
        "client_ip",
        "source_port",
        "user_agent",
        "tls_version",
        "tls_cipher"
      ],
      "properties": {
        "client_ip": {
          "type": "string",
          "oneOf": [
            { "format": "ipv4" },
            { "format": "ipv6" }
          ]
        },
        "source_port": {
          "type": "integer",
          "minimum": 1024,
          "maximum": 65535
        },
        "user_agent": { "type": "string" },
        "tls_version": { "type": "string" },
        "tls_cipher": { "type": "string" },
        "geolocation": {
          "type": "object",
          "properties": {
            "country_code": { "type": "string", "maxLength": 2 },
            "city": { "type": "string" },
            "latitude": { "type": "number" },
            "longitude": { "type": "number" },
            "isp": { "type": "string" }
          }
        }
      }
    },
    "consent_evidence": {
      "type": "object",
      "required": [
        "explicit_consent_checked",
        "consent_statement",
        "otp_channels"
      ],
      "properties": {
        "explicit_consent_checked": {
          "type": "boolean",
          "const": true,
          "description": "Debe ser estrictamente verdadero para registrar consentimiento activo e indubitable."
        },
        "consent_statement": {
          "type": "string",
          "description": "Texto legal exacto mostrado al usuario donde autoriza la firma del PDF específico."
        },
        "otp_channels": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": [
              "channel_type",
              "destination",
              "otp_sent_timestamp",
              "otp_verified_timestamp",
              "provider_message_id",
              "otp_code_hash"
            ],
            "properties": {
              "channel_type": {
                "type": "string",
                "enum": ["WHATSAPP", "SMS", "EMAIL"]
              },
              "destination": {
                "type": "string",
                "description": "Número de teléfono en formato E.164 o correo electrónico ofuscado."
              },
              "otp_sent_timestamp": {
                "type": "string",
                "format": "date-time"
              },
              "otp_verified_timestamp": {
                "type": "string",
                "format": "date-time"
              },
              "provider_message_id": {
                "type": "string",
                "description": "ID de transacción de la plataforma de mensajería externa (Ej. Twilio, Infobip) que actúa como tercero de confianza."
              },
              "otp_code_hash": {
                "type": "string",
                "description": "Hash SHA-256 del código enviado para evitar su almacenamiento en texto plano."
              }
            }
          }
        }
      }
    },
    "cryptographic_evidence": {
      "type": "object",
      "required": [
        "original_pdf_sha256",
        "signed_pdf_sha256",
        "user_certificate_serial",
        "ca_intermediate_serial",
        "signature_format",
        "tsa_evidence"
      ],
      "properties": {
        "original_pdf_sha256": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$",
          "description": "Hash SHA-256 del binario original del PDF recibido."
        },
        "signed_pdf_sha256": {
          "type": "string",
          "pattern": "^[a-f0-9]{64}$",
          "description": "Hash SHA-256 del binario del PDF resultante tras la firma incremental."
        },
        "user_certificate_serial": {
          "type": "string",
          "description": "Número de serie del certificado efímero X.509 v3 generado dinámicamente para el usuario."
        },
        "ca_intermediate_serial": {
          "type": "string",
          "description": "Número de serie de la CA Intermedia del PSCNC residente en AWS KMS."
        },
        "signature_format": {
          "type": "string",
          "const": "PAdES-T",
          "description": "Estándar de firma criptográfica con estampado de tiempo de Paraguay."
        },
        "tsa_evidence": {
          "type": "object",
          "required": [
            "tsa_provider_name",
            "tsa_certificate_chain",
            "rfc3161_response_base64",
            "timestamp_utc"
          ],
          "properties": {
            "tsa_provider_name": {
              "type": "string",
              "description": "Nombre del Prestador Cualificado de Servicios de Confianza (PCSC) local de donde se adquirió la marca de tiempo (Ej: Confirma, VIT S.A.)."
            },
            "tsa_certificate_chain": {
              "type": "array",
              "items": { "type": "string" },
              "description": "Cadena de certificados de la Autoridad de Sellado de Tiempo (TSA) para validación offline."
            },
            "rfc3161_response_base64": {
              "type": "string",
              "description": "Token binario completo de la respuesta del servicio de sellado de tiempo codificado en Base64."
            },
            "timestamp_utc": {
              "type": "string",
              "format": "date-time"
            }
          }
        }
      }
    }
  }
}
```

---

## 3. Modelo de Validación en Python (Pydantic V2)

Para asegurar la integridad de la base de datos a nivel de backend, Claude AI puede implementar el siguiente modelo de validación de **Pydantic** antes de serializar y persistir el documento de evidencias en Amazon DynamoDB:

```python
from datetime import datetime, date
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, EmailStr, IPvAnyAddress

class LivenessMeta(BaseModel):
    liveness_vendor: str
    liveness_confidence: float = Field(..., ge=0.0, le=1.0)
    spoof_check_passed: bool

class IdentityEvidence(BaseModel):
    document_type: Literal["CI_PY", "PASAPORTE"]
    national_id: str = Field(..., pattern=r"^[0-9]+$")
    first_name: str
    last_name: str
    birth_date: date
    ocr_mrz_raw: str
    ocr_confidence: float = Field(..., ge=0.0, le=1.0)
    facial_match_score: float = Field(..., ge=0.0, le=1.0)
    liveness_detected: bool
    liveness_meta: Optional[LivenessMeta] = None
    verification_partner_id: str

class Geolocation(BaseModel):
    country_code: str = Field(..., max_length=2)
    city: str
    latitude: float
    longitude: float
    isp: str

class NetworkEvidence(BaseModel):
    client_ip: IPvAnyAddress
    source_port: int = Field(..., ge=1024, le=65535)
    user_agent: str
    tls_version: str
    tls_cipher: str
    geolocation: Optional[Geolocation] = None

class OtpLog(BaseModel):
    channel_type: Literal["WHATSAPP", "SMS", "EMAIL"]
    destination: str
    otp_sent_timestamp: datetime
    otp_verified_timestamp: datetime
    provider_message_id: str
    otp_code_hash: str = Field(..., description="SHA-256 hash del OTP de un solo uso")

class ConsentEvidence(BaseModel):
    explicit_consent_checked: Literal[True]
    consent_statement: str
    otp_channels: List[OtpLog] = Field(..., min_items=1)

class TsaEvidence(BaseModel):
    tsa_provider_name: str
    tsa_certificate_chain: List[str]
    rfc3161_response_base64: str
    timestamp_utc: datetime

class CryptographicEvidence(BaseModel):
    original_pdf_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    signed_pdf_sha256: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    user_certificate_serial: str
    ca_intermediate_serial: str
    signature_format: Literal["PAdES-T"]
    tsa_evidence: TsaEvidence

class PSCNCAuditTrailItem(BaseModel):
    PK: str = Field(..., pattern=r"^TX#[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$")
    SK: str = Field(..., pattern=r"^METADATA#V[0-9]+$")
    GSI1PK: str = Field(..., pattern=r"^CI#PY-[0-9]+$")
    GSI1SK: datetime
    GSI2PK: str = Field(..., pattern=r"^CLIENT#[a-zA-Z0-9_.-]+$")
    GSI2SK: datetime
    
    transaction_id: str
    b2b_client_id: str
    status: Literal["INITIALIZED", "ONBOARDING_COMPLETED", "SIGNING_COMPLETED", "FAILED", "REVOKED", "COMPROMISED"]
    created_at: datetime
    completed_at: datetime
    
    identity_evidence: IdentityEvidence
    network_evidence: NetworkEvidence
    consent_evidence: ConsentEvidence
    cryptographic_evidence: CryptographicEvidence
```

---

## 4. Alineación Probatoria frente al Código Procesal Civil de Paraguay

Para que este registro sea indubitable ante los juzgados civiles y comerciales de la República del Paraguay, el sistema de auditoría debe estructurarse para responder metodológicamente a las preguntas de una **pericia informática forense oficial**:

1.  **Garantía de No Alteración (Integridad):** 
    *   *Defensa:* Al almacenar de forma inmutable el `original_pdf_sha256` y el `signed_pdf_sha256` en Amazon S3 Object Lock, y contrastarlos contra los hashes en el momento de la pericia, se demuestra de forma matemática que el documento no sufrió modificaciones desde el momento exacto de la firma (requisito exigido por el **Art. 39 de la Ley N.º 6822/2021**).
2.  **Vinculación Unívoca al Firmante (Autoría):** 
    *   *Defensa:* El objeto `identity_evidence` asocia la firma al número de cédula del ciudadano paraguayo tras un onboarding biométrico con prueba de vida (*liveness*). La correlación del `facial_match_score` y la verificación contra fuentes oficiales demuestra la debida diligencia de tu plataforma y vincula de forma unívoca la clave privada temporal utilizada con la persona física real.
3.  **Control Exclusivo (Voluntad):**
    *   *Defensa:* El objeto `consent_evidence` demuestra que el usuario mantenía el control exclusivo de sus medios de autenticación en el instante de la firma. Al verificar el código OTP enviado a un celular validado (vía WhatsApp/SMS), y registrar las IPs de red y puertos de conexión que coinciden temporalmente, se prueba que el acto de firma emanó de su acción directa y consciente.
4.  **Fecha Cierta (Hora Oficial del Acto):**
    *   *Defensa:* El objeto `tsa_evidence` inyecta un token **RFC 3161** provisto por una Autoridad de Sellado de Tiempo (TSA) cualificada de Paraguay. Esto independiza la marca temporal del reloj del servidor de tu plataforma (que podría ser alterado o hackeado) y la vincula de forma irrefutable al reloj de alta precisión de un tercero cualificado homologado por el MIC.

---

## 5. Instrucciones de Carga Directa para Claude AI

Para materializar este diseño, puedes copiar y pegar el siguiente comando instruccional dentro de tu sesión activa de **Claude AI**:

> **PROMPT PARA CLAUDE AI:**
> *"Actúa como un Arquitecto de Cloud & DevOps especializado en AWS y Criptografía. Utilizando el diseño de base de datos detallado en el documento `PSCNC_Audit_Trail`, genera de forma automatizada:
> 1. Un archivo de configuración de **Terraform** (`main.tf`) para desplegar la tabla `PSCNC_Audit_Trail` en Amazon DynamoDB utilizando el esquema de Single-Table design con GSIs, Point-in-Time Recovery (PITR) habilitado, y encriptación SSE-KMS.
> 2. Un script en **Python** utilizando el SDK oficial **`boto3`** que demuestre cómo insertar un registro completo que cumpla con el esquema JSON definido, manejando el mapeo de tipos nativos de DynamoDB (ej. números, strings, booleanos y mapas JSON).
> 3. Una función lambda de validación en Python que reciba el JSON de la transacción, verifique su conformidad con el modelo de Pydantic V2 y levante alertas en CloudWatch si falla la verificación."*
