# FirmasNoCualificadas (FNC) — plataforma B2B de firma electrónica no cualificada

SaaS multi-tenant que presta el servicio de firma electrónica no cualificada a terceros,
operando como **Prestador de Servicios de Confianza No Cualificado (PSCNC)** bajo la
Ley N.º 6822/2021 de Paraguay. Diseñado desde el primer día para salir de Paraguay: la
jurisdicción es **configuración, no código** (ADR-0008).

**La distinción que define el encuadre legal del proyecto:** un servicio de confianza es el
que se presta *habitualmente a cambio de una remuneración*. Un sistema que firma sus propias
contrataciones es un mecanismo interno y no se registra; FNC presta el servicio a terceros y
**por eso el registro ante el MIC no es opcional**. Todo lo que se construya acá vive del
lado del prestador.

---

## Fuente de verdad

| Qué | Dónde |
| :---- | :---- |
| Decisiones de arquitectura vigentes | `docs/adr/` — **no se reabren sin un ADR nuevo que las reemplace** |
| Diseño de negocio y normativo | `docs/diseno/`, con `docs/diseno/INDICE.md` como guía |
| Lo que **no** está resuelto | `docs/PENDIENTES.md` |
| Procedimiento de emergencia de claves | `docs/RUNBOOK-break-glass.md` |
| Ruta regulatoria ante el MIC | `docs/CUMPLIMIENTO-MIC.md` |

**Regla de trabajo con las normas.** Nunca cites de memoria un artículo de ley. La cita sale
de `docs/diseno/` y, en el código, del perfil de jurisdicción. Si una norma no tiene su texto
oficial en el repositorio, **es una cita que nadie puede contrastar**: está en la tabla §2 de
`docs/PENDIENTES.md` y se la trata como pendiente, no como respaldo.

Si algo que se pide no tiene respaldo en los documentos de diseño ni en un ADR, decilo
explícitamente: *«esto es una decisión de producto, no una obligación legal»*.

---

## Comandos

```bash
make setup            # entorno Python con uv + dependencias del dashboard con pnpm
make test             # lint + batería completa del backend
make lint             # ruff check, ruff format --check y mypy
make lint-dashboard   # ESLint y tsc del panel B2B
make run-api          # API B2B en http://localhost:8080
make security         # bandit + checkov
make tf-validate      # valida el Terraform del entorno ENV (por defecto dev)
make tf-plan          # plan del entorno ENV
```

**Antes de cualquier commit:** `make test` tiene que pasar. Incluye `mypy --strict`, que hoy
está limpio: mantenerlo así es parte del trabajo, no una tarea aparte.

### Gestión de paquetes

- **Python: `uv`**, con `services/uv.lock` versionado. No se usa `pip install` suelto.
- **Node: `pnpm` vía Corepack**, con `ignore-scripts=true` en el `.npmrc` de cada paquete.
  **Nunca `npm install`.** Es la política del equipo contra ataques de cadena de suministro:
  los scripts `postinstall` son el vector de los paquetes comprometidos. Si un paquete
  legítimamente necesita el suyo, se habilita individualmente con `pnpm approve-builds` y
  queda registrado en el control de versiones.

---

## Stack

- **Python 3.12** + **FastAPI** — API B2B
- **pyHanko** — firma PAdES incremental y sellado RFC 3161 (ADR-0001)
- **asn1crypto** — construcción del `TBSCertificate` (la firma es externa: la hace KMS)
- **Pydantic v2** — validación de evidencia; **structlog** — logs estructurados
- **DynamoDB** tabla única + **S3 Object Lock** en modo COMPLIANCE (ADR-0003)
- **AWS KMS** — CA intermedia, sellos por tenant y cifrado de evidencias (ADR-0006)
- **Terraform ≥ 1.9**, estado remoto en S3 con bloqueo en DynamoDB (ADR-0002)
- **React 18 + Vite + Tailwind** — panel B2B
- **pytest** + **moto** para las pruebas; **ruff** y **mypy --strict**

---

## Estructura

```
services/src/pscnc/
  orchestrator/     app FastAPI, máquina de estados, autenticación HMAC
  crypto/           ca_signer (KMS/local), ephemeral_ca, pades, tsa
  compliance/       legal_guard: actos jurídicos excluidos
  repositories/     DynamoDB y S3 — único lugar que habla con esos SDK
  models/           contratos de API y esquema de la pista de auditoría
  evidence/         expediente de evidencias
  onboarding/       cliente del proveedor de identidad del tenant
  jobs/             publicación de CRL
jurisdictions/      perfiles por país — el ÚNICO lugar con literales de norma (ADR-0008)
infra/terraform/    módulos por dominio, composición por entorno
api/openapi.yaml    contrato público
sdk/typescript/     SDK de referencia y tests de contrato para adaptadores de tenant
dashboard/          panel B2B y folleto forense
docs/               ADR, diseño, pendientes, runbooks
```

**Regla dura de capas.** Ningún módulo fuera de `repositories/` habla con el SDK de DynamoDB
o S3; ningún módulo fuera de `crypto/` llama a KMS. Todo lo demás depende de contratos.

---

## Reglas de negocio inviolables

Tienen consecuencia legal. El código debe hacerlas **imposibles de violar**, no solo
evitarlas. Cada una lleva su test asociado; **las marcadas `PENDIENTE` no están cubiertas
todavía y la fase que las cubre es parte del trabajo, no un extra.**

### Heredadas del primer tenant (invariantes de producto)

1. **Solo el hash del OTP se persiste.** Nunca el código en claro: ni en base, ni en logs, ni
   en respuestas de API, ni en el acta. En modo `TENANT_VERIFIED` el tenant envía la
   referencia del OTP, jamás el código.
   → `test_audit_trail_model.py::test_rechaza_hash_de_otp_que_no_sea_sha256`,
   `::test_rechaza_otp_verificado_antes_de_enviarse`

2. **Atomicidad del acto de firma.** Una transacción se firma entera o no se firma. No existe
   el estado en que una parte quedó firmada y otra no, y una confirmación repetida devuelve
   el acta original, nunca una nueva.
   → `test_signing_flow.py::test_no_admite_doble_firma`

3. **El documento se cierra y se hashea antes de habilitar la firma.** Cualquier modificación
   posterior invalida el paquete: hay que regenerar versión y huella. La versión viaja
   siempre junto al hash — una huella suelta no dice contra qué comparar.
   → `test_audit_trail_model.py::test_rechaza_hashes_identicos`

4. **Datos sensibles aislados.** Biometría, cédula, declaraciones de salud y condición PEP no
   salen hacia analítica, monitoreo de errores, CRM ni servicios de IA. Si agregás
   instrumentación, excluí explícitamente esos campos.
   → **PENDIENTE** (fase 6)

5. **Evidencia append-only.** Nunca se sobrescribe ni se borra un registro. Una corrección
   escribe `METADATA#V{n+1}`; el repositorio no expone borrado ni actualización, y la
   escritura lleva `attribute_not_exists` para que la evidencia no se pise.
   → cubierto por construcción en `dynamo_audit.py`; **falta el test explícito** (fase 5)

### Aislamiento multi-tenant

6. **El inquilino se deriva de la credencial, nunca del cuerpo de la petición**, y la
   comprobación vive en el repositorio, no solo en HTTP: un error de enrutamiento no puede
   convertirse en una fuga entre tenants. No se expone ninguna operación de `Scan`.
   → `test_security.py::test_contexto_bloquea_acceso_cruzado_entre_inquilinos`,
   `test_signing_flow.py::test_otro_inquilino_no_accede_a_la_transaccion`

7. **Una operación sobre el tenant A no puede alcanzar la clave de KMS del tenant B.**
   → **PENDIENTE** (fase 4, con `moto`/LocalStack)

### Custodia de claves (ADR-0006)

8. **Ningún rol humano tiene `kms:Sign`.** Quien puede firmar puede fabricar evidencia.
   → **PENDIENTE** (fase 4)

9. **La clave se selecciona por alias versionado, nunca por `KeyId` fijo.** Un `KeyId`
   cableado convierte cada rotación en un despliegue.
   → **PENDIENTE** (fase 4)

10. **Toda operación simétrica lleva `kms:EncryptionContext` con `tenant_id` y
    `transaction_id`,** exigido por condición en la política de clave.
    → **PENDIENTE** (fase 4)

11. **La retención de S3 Object Lock sale del perfil de jurisdicción y el `plan` de Terraform
    falla si es menor al mínimo.** En modo COMPLIANCE la retención es irreversible: un valor
    equivocado no se corrige, se hereda.
    → **PENDIENTE** (fase 4)

12. **Sin fecha cierta no hay firma de nivel 2.** Si la TSA falla, la transacción falla
    completa: nunca se degrada en silencio a PAdES-B-B. Un certificado efímero sin sello de
    tiempo es inverificable apenas expira.
    → **PENDIENTE** (fase 7)

### Jurisdicción y contrato con el tenant

13. **Ningún literal de norma, país u organismo fuera de `jurisdictions/`.**
    → **PENDIENTE** (fase 3, con test que recorre el árbol de código)

14. **FNC no vuelve a decidir la identidad.** Recibe la decisión del tenant y la asienta como
    evidencia. El umbral propio es informativo, no un control (ADR-0009).
    → **PENDIENTE** (fase 6)

15. **Todo error devuelve un motivo enumerado y estable**, nunca un mensaje libre: el tenant
    tiene que poder mapearlo a su máquina de estados.
    → parcialmente cubierto por `errors.py`; **falta el test de estabilidad** (fase 6)

---

## Máquina de estados de la transacción

```
INITIALIZED ──confirm()──► SIGNING_COMPLETED
     │
     ├── expiración ──► FAILED
     └── error ───────► FAILED

SIGNING_COMPLETED ──► REVOKED | COMPROMISED   (fuera del flujo, por incidente)
```

Reglas que gobiernan las transiciones:

- Solo se firma si el `identity_decision` del tenant viene aprobado (ADR-0009).
- Solo se firma si el `legal_guard` de la jurisdicción activa no detecta un acto excluido.
- **Primero se consolida la evidencia, después se publica el documento firmado.** Si la
  evidencia no se persiste, el documento **no se entrega**: un documento firmado sin pista de
  auditoría es un pasivo, no un activo.
- `COMPROMISED` no es un fallo técnico: marca una transacción sobre la que se denunció robo
  de identidad. La evidencia no se borra, se anota.

Toda transición pasa por `orchestrator/state_machine.py`. **Ningún handler de FastAPI
modifica el estado directamente.**

---

## Niveles de servicio (ADR-0007)

| | **Nivel 1** | **Nivel 2** |
| :---- | :---- | :---- |
| Qué recibe | Hash del documento (por defecto) o PDF | Necesita el PDF |
| Qué hace | Acta de evidencia sellada con KMS | Lo del nivel 1 **más** firma PAdES con certificado efímero y sello RFC 3161 |
| El PDF | **No se modifica** | Se firma incrementalmente y se devuelve; no se conserva salvo custodia contratada |
| Qué verifica un tercero | El acta, con la clave pública publicada | El acta **y** el archivo, con cualquier validador PAdES |

El recorrido del firmante es idéntico en ambos: el nivel es una propiedad del contrato. El
nivel 2 **no puede ofrecerse en producción** hasta que se cumplan los tres bloqueantes de
`docs/PENDIENTES.md` §1.

---

## Puertos y adaptadores

Los proveedores externos viven detrás de contratos:

`CaSigner` (KMS / local) · `TimeStamperDelegate` (TSA) · `OnboardingClient` ·
`SecretResolver` (Secrets Manager / estático) · `AuditTrailRepository` · `DocumentVault`

La selección se hace en `orchestrator/dependencies.py`, **único lugar** donde se decide qué
implementación se usa. Fuera de ahí, el código depende de contratos.

Los backends de desarrollo (`LocalCaSigner`, `SandboxOnboardingClient`, TSA de prueba) están
**prohibidos en `staging` y `prod` por validación de configuración**, que falla al arrancar.
Un servicio que firma documentos con valor jurídico no arranca con parámetros ambiguos.

---

## Checklist antes de cerrar una tarea

Además de `make test` en verde:

1. ¿La regla implementada tiene respaldo en un ADR o en `docs/diseno/`? Si no, ¿está marcada
   como decisión de producto y no como obligación legal?
2. ¿Se introdujo algún literal de norma, país u organismo fuera de `jurisdictions/`?
3. ¿La evidencia correspondiente se persiste antes de entregar cualquier artefacto?
4. ¿La operación exige contexto de tenant y lo verifica en el repositorio, no solo en HTTP?
5. Si toca KMS: ¿selecciona la clave por alias? ¿lleva `EncryptionContext` completo?
   ¿queda registrada en CloudTrail?
6. ¿Algún código de OTP, dato biométrico, cédula o dato de salud quedó en un log, en una
   respuesta de API o en el acta?
7. Si cambia el contrato público: ¿se actualizó `api/openapi.yaml`, el SDK y los tests de
   contrato? ¿el cambio es compatible hacia atrás para los tenants existentes?
8. Si algo quedó sin resolver, ¿está en `docs/PENDIENTES.md` en lugar de simulado en silencio?

---

## Qué no hacer

- **No reabrir un ADR sin escribir el ADR que lo reemplaza.** Las decisiones de `docs/adr/`
  están vigentes.
- **No inventar artículos de ley, OID, endpoints ni campos de API.** Si no está en los
  documentos fuente, no existe: se pregunta o se registra como pendiente.
- **No simular un pendiente en silencio.** Un artefacto de desarrollo que parece de
  producción es peor que uno que falta: alguien lo va a presentar como si fuera válido. Por
  eso `dev` etiqueta `environment=dev` y `tsa=test` en cada certificado y en cada acta.
- **No usar `Any` en Python ni `any` en TypeScript.** El dominio de la evidencia es de tipado
  estricto: un `Any` en una estructura probatoria es una estructura sin verificar.
- **No agregar un `# type: ignore` sin comentario que explique por qué.** Los dos que existen
  documentan funciones que pyHanko no anota.
- **No usar `npm install`** ni habilitar scripts de instalación de paquetes.
- **No escribir lógica de negocio en los handlers de FastAPI** — va en `orchestrator/` y
  `compliance/`.
- **No hacer commits que dejen la batería en rojo.**
- **No ejecutar `terraform apply` contra una cuenta real** sin autorización explícita.
