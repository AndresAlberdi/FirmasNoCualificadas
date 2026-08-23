# Arquitectura del Sistema FENC-PY

Documento vivo. Toda modificación estructural exige un ADR nuevo en `docs/adr/` y, si
altera algoritmos, custodia de claves o perfiles de certificado, la actualización de la
**Declaración de Prácticas de los Servicios de Confianza (DPSC)** presentada ante la DGFDCE.

---

## 1. Contexto y límites del sistema

El sistema **no** realiza el onboarding de identidad: consume un módulo preexistente que
entrega captura de cédula, OCR/MRZ, selfie, biometría con prueba de vida, verificación de
WhatsApp/correo y contraste AML/PEP. La plataforma FENC-PY comienza cuando ese módulo
emite un `onboarding_token` con estado `APPROVED`.

```
┌───────────────┐        ┌──────────────────────────────┐        ┌──────────────────┐
│ Cliente B2B   │──API──►│   PLATAFORMA FENC-PY (AWS)   │──RFC──►│ TSA cualificada  │
│ (aseguradora, │        │                              │  3161  │ PCSC Paraguay    │
│  banco, etc.) │◄───────│                              │◄───────│                  │
└───────────────┘        └───────────┬──────────────────┘        └──────────────────┘
                                     │ token de onboarding
                                     ▼
                         ┌──────────────────────────────┐
                         │ Módulo de Onboarding (extern)│
                         │ biometría · OCR · AML/PEP    │
                         └──────────────────────────────┘
```

**Fuera de alcance de esta plataforma:** emisión de certificados cualificados, dispositivo
cualificado de creación de firma (QSCD), y actos jurídicos excluidos por ley de la firma
electrónica simple.

---

## 2. Vista de componentes

| Componente | Runtime | Responsabilidad | Módulo |
| :-- | :-- | :-- | :-- |
| **API Edge** | API Gateway + WAF | TLS 1.3, mTLS opcional, rate limiting por tenant, reglas OWASP | `infra/.../api-edge` |
| **Orchestrator** | ECS Fargate (FastAPI) | Máquina de estados de la sesión de firma, autenticación B2B, orquestación | `pscnc.orchestrator` |
| **Compliance Guard** | in-process | Bloqueo de actos jurídicos excluidos y validación de umbrales biométricos | `pscnc.compliance` |
| **Crypto Engine** | in-process | Emisión de certificado efímero, firma incremental PAdES, sellado TSA | `pscnc.crypto` |
| **Evidence Builder** | in-process | Consolidación del expediente forense en PDF y su sellado | `pscnc.evidence` |
| **Audit Store** | DynamoDB + S3 Object Lock | Persistencia inmutable de la pista de auditoría | `pscnc.repositories` |
| **CRL Publisher** | Lambda + EventBridge | Regeneración y publicación diaria de la CRL firmada por KMS | `pscnc.jobs.crl_publisher` |
| **Dashboard B2B** | CloudFront + S3 (SPA) | Folleto forense, explorador de transacciones, gestión de credenciales | `dashboard/` |

---

## 3. Flujo crítico: firma de un documento

```
 (1) POST /v1/signing-sessions            (2) Validaciones previas
     ├─ onboarding_token                      ├─ onboarding APPROVED
     ├─ pdf_document                          ├─ facial_match_score ≥ 0.95
     └─ metadata                              ├─ liveness_detected = true
            │                                 └─ Compliance Guard: acto no excluido
            ▼                                        (403 si "hipoteca", "testamento"…)
   [ SHA-256 del PDF original ] ──► DynamoDB estado INITIALIZED
            │
 (3) POST /v1/signing-sessions/{id}/confirm  (consentimiento OTP verificado)
            │
            ▼
   [ Par de claves efímero RSA-2048 en memoria del contenedor ]
            │
            ▼
   [ TBSCertificate X.509 v3 ] ──hash──► AWS KMS Sign ──► Certificado del firmante
            │                            (clave de la CA nunca sale del HSM)
            ▼
   [ pyHanko: actualización incremental del PDF, /ByteRange, CMS SignedData ]
            │
            ▼
   [ Hash del SignatureValue ] ──RFC 3161──► TSA cualificada PY ──► token
            │                                                        │
            └──────────► atributo no firmado signature-time-stamp ◄──┘
            │
            ▼
   [ SHA-256 del PDF firmado ] ──► S3 signed-vault (SSE-KMS)
   [ Expediente de evidencias PDF ] ──► S3 evidence-trail (Object Lock, 2 años)
   [ Item completo ] ──► DynamoDB estado SIGNING_COMPLETED
            │
            ▼
   [ Destrucción de la clave privada efímera ]   ← invariante no negociable
```

### 3.1 Invariantes del flujo

1. La clave privada efímera existe únicamente en memoria del proceso y jamás se
   serializa, registra ni persiste. Su ciclo de vida es el de una sola transacción.
2. La clave de la CA Intermedia nunca abandona AWS KMS; solo se invoca `kms:Sign` sobre
   un digest de 32 bytes.
3. Ninguna escritura de evidencia puede realizarse después de marcar la sesión como
   `SIGNING_COMPLETED`; toda corrección genera una versión nueva (`METADATA#V2`).
4. Si el sellado de tiempo falla, la transacción falla completa: **no se entrega una
   firma sin fecha cierta**. PAdES-B-T es el nivel mínimo aceptable.

---

## 4. Modelo de datos forense

Tabla única `PSCNC_Audit_Trail` en DynamoDB, detallada en
[`blueprints/esquema-base-datos-auditoria-pscnc.md`](blueprints/esquema-base-datos-auditoria-pscnc.md)
y materializada en `pscnc.models.audit_trail`.

| Índice | PK | SK | Consulta que habilita |
| :-- | :-- | :-- | :-- |
| Tabla | `TX#{uuid}` | `METADATA#V{n}` | Acceso atómico a una sesión |
| GSI1 | `CI#PY-{cedula}` | ISO-8601 | Todas las firmas de un ciudadano (pericia) |
| GSI2 | `CLIENT#{tenant}` | ISO-8601 | Reportes y facturación por cliente B2B |

Los cuatro pilares de la pericia se mapean a cuatro objetos: `identity_evidence` (quién),
`consent_evidence` (voluntad), `network_evidence` (dónde) y `cryptographic_evidence` (qué).

---

## 5. Seguridad transversal

* **Autenticación B2B:** HMAC-SHA256 sobre `{método}\n{path}\n{timestamp}\n{sha256(body)}`
  con ventana de 300 s, o mTLS cuando el cliente lo soporte. Secreto en Secrets Manager
  con rotación automática de 90 días.
* **Aislamiento multi-tenant:** todo acceso a datos exige `b2b_client_id` y se valida
  contra el sujeto autenticado (ADR-0005). No existe consulta sin partición de tenant.
* **Cifrado:** TLS 1.3 en tránsito; SSE-KMS con clave gestionada por el cliente en reposo
  para DynamoDB, S3 y logs.
* **Retención:** mínimo 2 años desde el vencimiento de los efectos jurídicos del documento,
  con S3 Object Lock en modo Compliance (irreversible incluso para el rol raíz).
* **Trazabilidad:** CloudTrail con validación de integridad del log, alarmas sobre
  `kms:Sign` anómalo, GuardDuty y notificación SNS al canal de SecOps.

---

## 6. Modos degradados

| Fallo | Comportamiento | Justificación |
| :-- | :-- | :-- |
| TSA cualificada no responde | Reintento exponencial (3 intentos); si persiste, `FAILED` y se libera la sesión | Sin fecha cierta la evidencia pierde su valor diferencial |
| KMS `ThrottlingException` | Reintento con jitter; alarma si supera el umbral | La firma es idempotente por `signing_session_id` |
| Onboarding externo no disponible | Rechazo `503`, sin crear sesión | No se firma sin identidad verificada |
| DynamoDB no confirma la escritura de evidencia | Rollback lógico: el PDF firmado no se entrega | Un documento firmado sin pista de auditoría es un pasivo legal |

---

## 7. Deuda técnica reconocida (backlog priorizado)

1. **PAdES-B-LTA:** falta la recolección OCSP/CRL de la cadena, la escritura del
   diccionario `/DSS` y el archive timestamp. Requisito para contratos de larga duración.
2. **Sello electrónico de persona jurídica** sobre el expediente de evidencias: depende de
   la contratación de un certificado de sello con un PCSC cualificado paraguayo.
3. **mTLS extremo a extremo** en API Gateway: pendiente de definir la CA de clientes B2B.
4. **Firma visible con apariencia normalizada** (grafo, sello, texto legal) parametrizable
   por tenant.
5. **Pruebas de validación cruzada** con Adobe Acrobat, EU DSS Validator y validador del MIC.
