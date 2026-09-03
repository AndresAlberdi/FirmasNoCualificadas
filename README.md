# FENC · Motor de Firma Electrónica No Cualificada, embebible

Monorepo del motor que emite **Firmas Electrónicas No Cualificadas (FENC)** sobre documentos
PDF bajo el estándar **PAdES-B-T**, pensado para que **una organización lo despliegue en su
propia infraestructura y firme sus propias contrataciones**.

**No es un servicio de firma y no se presta a terceros.** La Ley N.º 6822/2021 define el
servicio de confianza como el prestado *habitualmente a cambio de una remuneración*
(art. 4.º num. 48) y dirige a los **prestadores** la obligación de comunicar su actividad
(art. 15). Quien firma lo suyo es un mecanismo interno y no se registra. El encuadre completo,
con la condición arquitectónica de la que depende, está en el **ADR-0011**.

> El valor probatorio de una FENC no proviene del certificado, sino de la **pista de
> auditoría**. El art. 39.2 de la ley reserva la equivalencia con la firma manuscrita a la
> firma *cualificada*: una firma no cualificada nunca la tiene, y lo que se exhibe cuando se
> impugna su autenticidad —art. 40, que remite al art. 404 del Código Civil— es el expediente
> de evidencias. Todo el diseño de este repositorio está subordinado a ese objetivo.

---

## 1. Mapa del repositorio

```
FirmasNoCualificadas/
├── docs/                     Documentación normativa, arquitectura y ADRs
│   ├── ARQUITECTURA.md       Vista 4+1 del sistema y flujos críticos
│   ├── CUMPLIMIENTO-MIC.md   Ruta administrativa REPSE → DGFDCE
│   ├── RUNBOOK-break-glass.md Procedimiento de compromiso de la CA
│   ├── adr/                  Architecture Decision Records
│   └── diseno/               Documentos de diseño y normativos (ver diseno/INDICE.md)
├── infra/terraform/          Infraestructura como código (AWS)
│   ├── modules/              Módulos reutilizables por dominio
│   └── envs/{dev,prod}       Composición por entorno
├── services/                 Backend Python 3.12 (FastAPI + pyHanko)
│   └── src/pscnc/
│       ├── crypto/           Motor PAdES, CA efímera, KMS signer, TSA
│       ├── models/           Contratos Pydantic v2 (audit trail y API)
│       ├── repositories/     Persistencia DynamoDB / S3 Object Lock
│       ├── compliance/       Agente regulatorio (exclusiones legales)
│       ├── evidence/         Generación del expediente forense
│       └── orchestrator/     API B2B y máquina de estados
├── dashboard/                Frontend React + TypeScript + Tailwind
├── scripts/                  Utilidades de desarrollo y operación
└── .github/workflows/        CI/CD y controles de seguridad
```

## 2. Arquitectura en una línea

```
Cliente B2B ──mTLS/HMAC──► API Gateway + WAF ──► Orchestrator (Fargate)
                                                      │
             ┌────────────────────────────────────────┼──────────────────────────┐
             ▼                    ▼                   ▼                          ▼
      Onboarding (externo)   KMS Intermediate CA   TSA cualificada PY     DynamoDB Audit Trail
      identidad + biometría  firma cert. efímero   RFC 3161 (PAdES-T)     S3 Object Lock (WORM)
```

Detalle completo en [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md).

## 3. Decisiones de arquitectura vigentes

| ADR | Decisión | Estado |
| :-- | :-- | :-- |
| [0001](docs/adr/0001-motor-de-firma-pyhanko.md) | Motor de firma: Python 3.12 + pyHanko con firma externa | Aceptado |
| [0002](docs/adr/0002-iac-terraform.md) | Infraestructura como código: Terraform | Aceptado |
| [0003](docs/adr/0003-single-table-dynamodb.md) | Persistencia forense: DynamoDB single-table + WORM en S3 | Aceptado |
| [0004](docs/adr/0004-certificados-efimeros-kms.md) | Certificados de firmante efímeros emitidos por CA en KMS | Aceptado |
| [0005](docs/adr/0005-aislamiento-multi-tenant.md) | Aislamiento multi-tenant lógico con partición por cliente | Aceptado |

## 4. Puesta en marcha local

Requisitos: Python 3.12, Node 20+, Terraform 1.9+, Docker, credenciales AWS con perfil
`pscnc-dev`.

```bash
make setup          # entorno virtual, dependencias de services/ y dashboard/
make test           # pytest + ruff + mypy
make run-api        # uvicorn en http://localhost:8080 (modo SANDBOX)
make run-dashboard  # vite en http://localhost:5173
make tf-plan ENV=dev
```

El backend arranca en modo `SANDBOX` con un firmante de prueba en archivo cuando
`PSCNC_CRYPTO_BACKEND=local`; nunca use ese modo fuera de desarrollo.

## 5. Estado actual del scaffolding

| Componente | Estado |
| :-- | :-- |
| Modelos de evidencia y validación Pydantic | Implementado |
| Emisión de certificado efímero X.509 firmado por KMS | Implementado |
| Firma PAdES-B-T incremental + TSA RFC 3161 | Implementado |
| Agente de cumplimiento (exclusiones Art. 4 Ley 6822/2021) | Implementado |
| API B2B `/v1/signing-sessions` | Implementado (integración de onboarding vía adaptador) |
| Expediente de evidencias PDF + sello de persona jurídica | Implementado el expediente; **sello corporativo pendiente de contrato con PCSC** |
| Terraform (7 módulos + entorno dev) | Implementado; requiere parámetros reales de cuenta |
| Dashboard Folleto Forense | Prototipo con datos simulados |
| PAdES-B-LTA (DSS/LTV + archive timestamp) | **Pendiente** — ver `docs/ARQUITECTURA.md §7` |

## 6. Advertencia legal

Este software no emite firmas electrónicas cualificadas ni sustituye a un Prestador
Cualificado de Servicios de Confianza. Antes de operar comercialmente debe completarse
la ruta administrativa descrita en [`docs/CUMPLIMIENTO-MIC.md`](docs/CUMPLIMIENTO-MIC.md),
incluida la notificación a la DGFDCE dentro de los tres (3) meses del inicio efectivo
de la prestación.
