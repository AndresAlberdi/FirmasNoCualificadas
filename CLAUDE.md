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
make tf-test          # pruebas de infraestructura (no necesitan credenciales)
make tf-jurisdiccion  # regenera jurisdiccion.auto.tfvars desde el perfil
make sdk-test         # pruebas de contrato del SDK de TypeScript
make openapi          # regenera api/openapi.yaml desde la aplicación
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
services/src/jurisdictions/
  profile.py        contrato de un perfil; py/ y bo/ los perfiles y sus textos
                    el ÚNICO lugar con literales de norma, país u organismo (ADR-0008)
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
   `::test_rechaza_otp_verificado_antes_de_enviarse`,
   `test_api_http.py::test_el_codigo_otp_no_vuelve_en_la_respuesta`

2. **Atomicidad del acto de firma.** Una transacción se firma entera o no se firma. No existe
   el estado en que una parte quedó firmada y otra no, y una confirmación repetida devuelve
   el acta original, nunca una nueva.
   → `test_signing_flow.py::test_no_admite_doble_firma`

3. **El documento se cierra y se hashea antes de habilitar la firma.** Cualquier modificación
   posterior invalida el paquete: hay que regenerar versión y huella. La versión viaja
   siempre junto al hash — una huella suelta no dice contra qué comparar.
   → `test_audit_trail_model.py::test_rechaza_hashes_identicos`

4. **Datos sensibles aislados.** Biometría, cédula, declaraciones de salud y condición PEP no
   salen hacia analítica, monitoreo de errores, CRM ni servicios de IA, ni viajan en el acta
   ni en la constancia pública. Si agregás instrumentación, excluí explícitamente esos campos.
   → `test_contrato_v1.py::TestDatosSensiblesAislados`,
   `test_acta_sellada.py::test_el_acta_no_contiene_datos_personales`

5. **Evidencia append-only.** Nunca se sobrescribe ni se borra un registro. Una corrección
   escribe `METADATA#V{n+1}`; el repositorio no expone borrado ni actualización, y la
   escritura lleva `attribute_not_exists` para que la evidencia no se pise.
   → `test_repositorios.py::test_no_sobrescribe_una_version_existente`,
   `::test_una_correccion_crea_una_version_nueva`

### Aislamiento multi-tenant

6. **El inquilino se deriva de la credencial, nunca del cuerpo de la petición**, y la
   comprobación vive en el repositorio, no solo en HTTP: un error de enrutamiento no puede
   convertirse en una fuga entre tenants. No se expone ninguna operación de `Scan`.
   → `test_security.py::test_contexto_bloquea_acceso_cruzado_entre_inquilinos`,
   `test_signing_flow.py::test_otro_inquilino_no_accede_a_la_transaccion`,
   `test_repositorios.py::test_no_se_puede_leer_la_transaccion_de_otro_inquilino`,
   `test_api_http.py::test_el_inquilino_sale_de_la_credencial_y_no_del_cuerpo`

7. **Una operación sobre el tenant A no puede alcanzar la clave de KMS del tenant B.**
   El aislamiento vive en la política de la clave, no en el código: si el contexto de
   cifrado no coincide, KMS se niega a descifrar aunque el llamador tenga permisos sobre
   ambas claves.
   → `test_tenant_keys.py::test_otro_inquilino_no_puede_descifrar`,
   `::test_el_sello_de_un_inquilino_no_valida_con_la_clave_de_otro`

### Custodia de claves (ADR-0006)

8. **Ningún rol humano tiene `kms:Sign`.** Quien puede firmar puede fabricar evidencia.
   Las políticas de `modules/kms-tenant-keys` conceden administración sin firma; el rol de
   servicio firma sin poder administrar.
   → revisión de política en `modules/kms-tenant-keys/main.tf`; alarma
   `kms_sign_unexpected_principal` en `modules/observability`

9. **La clave se selecciona por alias versionado, nunca por `KeyId` fijo.** Un `KeyId`
   cableado convierte cada rotación en un despliegue, y durante el solapamiento hacen falta
   las dos claves a la vez — la anterior verificando, la nueva firmando.
   → `test_tenant_keys.py::TestSeleccionPorAlias`

10. **Toda operación simétrica lleva `kms:EncryptionContext` con `tenant_id` y
    `transaction_id`,** exigido por condición en la política de clave. El contexto va
    autenticado con el texto cifrado: liga cada objeto a su inquilino y a su transacción
    sin depender de que el código lo compruebe.
    → `test_tenant_keys.py::test_el_contexto_de_cifrado_lleva_inquilino_y_transaccion`,
    `::test_no_se_puede_descifrar_en_otra_transaccion`

11. **La retención de S3 Object Lock sale del perfil de jurisdicción y el `plan` de Terraform
    falla si es menor al mínimo.** En modo COMPLIANCE la retención es irreversible: un valor
    equivocado no se corrige, se hereda. El mínimo lo exporta
    `scripts/exportar-jurisdiccion.py` desde el perfil, para que el dato tenga una sola
    fuente; los módulos toman la retención de la salida de `retention-gate`, de modo que la
    compuerta quede en el grafo de dependencias y no pueda saltearse por olvido.
    → `modules/retention-gate/tests/compuerta.tftest.hcl` (`make tf-test`)

12. **Sin fecha cierta no hay firma de nivel 2.** Si la TSA falla, la transacción falla
    completa: nunca se degrada en silencio a PAdES-B-B. El certificado del firmante vive
    quince minutos, así que un validador posterior lo encuentra expirado; lo único que
    acredita que la firma se produjo dentro de esa ventana es el sello de tiempo. Una firma
    sin él parece prueba y no lo es.
    → `test_nivel_2.py::TestSinFechaCiertaNoHayFirma`

### Jurisdicción y contrato con el tenant

13. **Ningún literal de norma, país u organismo fuera de `jurisdictions/`.** La regla
    se verifica sobre el árbol sintáctico y alcanza a los **valores**, no a los comentarios
    ni a la documentación: un comentario que cita la norma explica por qué existe una
    decisión; un valor que la cita emite un certificado.
    → `test_jurisdicciones.py::test_sin_literales_de_jurisdiccion_fuera_del_modulo`,
    con `::test_el_detector_encuentra_un_literal_prohibido` verificando el detector mismo

14. **FNC no vuelve a decidir la identidad.** Recibe la decisión del tenant y la asienta como
    evidencia. El umbral propio es informativo, no un control (ADR-0009).
    → `test_contrato_v1.py::TestIdentidadDelTenant`

15. **Todo error devuelve un motivo enumerado y estable**, nunca un mensaje libre: el tenant
    tiene que poder mapearlo a su máquina de estados. Agregar un motivo es compatible;
    renombrarlo rompe el `match` del tenant en silencio.
    → `test_contrato_v1.py::TestMotivosEstables`, más la suite de contrato del SDK

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

## Jurisdicciones (ADR-0008)

```python
from jurisdictions import require_profile

perfil = require_profile(settings.jurisdiction, environment=settings.environment)
perfil.signature_law_citation       # norma citada en la constancia
perfil.subject_serial_number(ci)    # serialNumber del certificado
perfil.signer_index_key(ci)         # clave del índice pericial
perfil.retention.minimum_days       # conservación mínima
perfil.text("firma.motivo")         # texto de producto
```

`require_profile` **se niega a devolver un perfil sin validación legal** en `staging` y
`prod`. Hoy `BO` es uno de esos: existe para demostrar que la arquitectura generaliza —su
documento admite complemento alfanumérico, así que rompe cualquier `^[0-9]+$` que hubiera
quedado escondido— y no para producir evidencia oponible. Sus campos normativos llevan
`[SIN VERIFICAR]` y no declara ninguna TSA, porque afirmar que un prestador está habilitado
sin comprobarlo sería inventarlo.

Agregar un país es agregar un paquete bajo `jurisdictions/` y una entrada en su registro.
**Si hace falta tocar el motor, el perfil está incompleto.**

---

## Niveles de servicio (ADR-0007)

| | **Nivel 1** | **Nivel 2** |
| :---- | :---- | :---- |
| Qué recibe | Hash del documento (por defecto) o PDF | Necesita el PDF |
| Qué hace | Acta de evidencia sellada con KMS | Lo del nivel 1 **más** firma PAdES con certificado efímero y sello RFC 3161 |
| El PDF | **No se modifica** | Se firma incrementalmente y se devuelve; no se conserva salvo custodia contratada |
| Qué verifica un tercero | El acta, con la clave pública publicada | El acta **y** el archivo, con cualquier validador PAdES |

**Fuera de producción, todo artefacto va marcado.** El certificado lleva
`[NO VALIDO - ENTORNO DEV]` en la unidad organizativa —un campo que cualquier visor muestra,
no una extensión que nadie mira— y el acta declara `environment` y
`not_valid_for_production`, más `timestamp.qualified: false` cuando el sello viene de una
autoridad de pruebas. Un sello de prueba acredita que el sistema funciona, no la fecha
cierta del acto.

**Las firmas posteriores no invalidan la del cliente.** La firma cualificada del corredor
—obligatoria por el art. 5 de la Res. SS.SG. 210/2025 en el caso del primer tenant— se
aplica como actualización incremental sobre el mismo archivo. Si la invalidara, habría que
elegir entre las dos, y ninguna es opcional.

El recorrido del firmante es idéntico en ambos: el nivel es una propiedad del contrato. El
nivel 2 **no puede ofrecerse en producción** hasta que se cumplan los tres bloqueantes de
`docs/PENDIENTES.md` §1.

---

## Contrato público v1 (ADR-0009)

```
POST /v1/transactions                 abre la transacción
POST /v1/transactions/{id}/confirm    confirma y sella el acta
GET  /v1/transactions/{id}/artifacts  recupera lo producido
GET  /v1/verify/{code}                constancia pública, SIN autenticación
GET  /.well-known/fnc-keys.json       claves públicas, SIN autenticación
```

Lo que un integrador tiene que entender antes de programar:

* **La identidad la decide el tenant.** FNC solo lee su veredicto. Dos controles sobre el
  mismo acto no se suman: gana el más laxo.
* **El OTP del tenant es evidencia, no control.** Viaja la referencia, nunca el código.
* **Hash-only por defecto.** Lo que no se recibe no se filtra.
* **`Idempotency-Key` obligatoria en las escrituras.** Una confirmación repetida devuelve el
  acta original: dos actas para un mismo acto son dos evidencias divergentes del mismo
  hecho, y eso sirve para impugnar las dos.
* **Los rechazos se leen por `motivo`**, nunca por el mensaje.

`api/openapi.yaml` se genera (`make openapi`) y se versiona: un cambio del contrato aparece
como diff en el PR, que es donde se nota que se rompió la compatibilidad de un tenant.

`sdk/typescript/` exporta `runFncContractTests`: la suite que un adaptador de tenant ejecuta
**contra sí mismo** para probar que cumple el contrato, en vez de afirmarlo.

---

## El acta sellada (ADR-0006 §6)

El artefacto que hace verificable al nivel 1, donde el documento no se modifica y lo único
que prueba el acto es el registro. Un registro que nosotros podemos reescribir no prueba
nada; el acta cierra ese hueco.

```python
sellada = ActaSealer(key_ring).seal(acta)
sellada.jws              # sobre compacto, con `kid` = alias versionado
sellada.payload_sha256   # SHA-256 del JSON canónico: es lo que se firmó
```

* **JSON canónico (RFC 8785).** Sin orden de claves determinista, dos serializaciones del
  mismo acta dan hashes distintos y la verificación falla por motivos ajenos a la
  integridad.
* **El acta no lleva datos personales**: huellas y referencias. Puede entregarse al
  inquilino y llegar a un juzgado.
* **`GET /.well-known/fnc-keys.json`** publica las claves públicas, sin autenticación y a
  propósito: un sello que solo nosotros sabemos comprobar no traslada confianza, la
  concentra.

**El detalle que rompe la interoperabilidad:** KMS devuelve ECDSA en **DER** y JWS `ES256`
exige `R‖S` en crudo (RFC 7518 §3.4). Un sobre con el DER dentro parece correcto, lo
verificaría nuestro propio código si compartiera el error, y **no lo acepta ninguna librería
estándar**. Por eso la prueba de interoperabilidad usa `jwcrypto`, ajena al sellador:
verificar con el mismo código que firma demuestra consistencia, no interoperabilidad.

**Cuidado con `moto` al tocar esto:** ignora `MessageType="DIGEST"` y vuelve a hashear,
mientras AWS firma el digest tal cual. Adaptar el código para que `moto` lo acepte rompería
la interoperabilidad real. El sellado se prueba contra un doble fiel a la semántica
documentada (T-10 en `docs/PENDIENTES.md`).

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

## Estándar DevSecOps v2

El repositorio aplica el estándar de `~/SeguridadGeneral` en **modo A** (público), stack
`multicloud` (tres componentes: `signer`, `infra`, `dashboard`). El manifiesto es
`.devsecops.yml` y el pipeline es `.github/workflows/ci-multicloud.yml`, con las ocho fases
fijas más el job agregador `compuerta-pr`.

### Reglas obligatorias antes de dar por terminada cualquier tarea

1. **Pruebas en verde**: ejecute la suite completa; si añade funcionalidad, añada pruebas.
   No marque una tarea como terminada con pruebas fallando o saltadas.
2. **`./security-local.sh` sin CRITICAL ni HIGH** no exceptuados. Si faltan herramientas,
   indíquelo explícitamente: **un análisis vacío no equivale a un análisis limpio.**
3. **Conventional Commits** (`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`,
   `build`, `ci`, `chore`, `security`, `revert`), descripción en español. Un cambio por
   commit; sin `--no-verify`.
4. **Nunca confirme secretos**: ni `.env`, ni claves, ni JSON de cuentas de servicio, ni
   tokens en código o workflows. Se referencian por nombre, nunca por valor. Si detecta uno
   en el historial, deténgase e informe.
5. **Nunca degrade reglas de seguridad de datos ni de IAM**: políticas de clave de KMS,
   políticas IAM, trust policies OIDC. Ampliar permisos exige justificación escrita en el PR
   y aprobación del propietario.
6. **Nunca despliegue a producción** ni cree el tag `vX.Y.Z` sin instrucción explícita de una
   persona. Prepare el pase y entregue los comandos para que los ejecute quien corresponda.
7. **No desactive controles**: no comente pasos de workflows, no añada `continue-on-error`,
   no relaje `bloquear_en`, no cree archivos de ignorado para ocultar hallazgos. Las
   excepciones van solo en `seguridad.excepciones` de `.devsecops.yml`, con `vence`, y las
   aprueba el propietario.
8. **Acciones fijadas por SHA** con comentario de versión en todo workflow que edite. **El
   SHA se verifica contra el repositorio de la acción antes de escribirlo** (`gh api
   repos/<owner>/<repo>/git/refs/tags/<tag>`): un SHA inventado no fija nada, rompe el
   workflow y es indistinguible de un error tipográfico en la revisión.
9. **Revise el diff antes de proponer el commit** (`git diff --cached`) y use
   `.github/PULL_REQUEST_TEMPLATE.md` al abrir PRs.

### Ante un hallazgo de seguridad

Lea `.security-reports/ultimo/resumen.md` y clasifique por severidad.

* **CRITICAL/HIGH:** corrija en la misma rama antes de continuar. Si es una dependencia,
  actualice a la versión con corrección; **si no hay corrección disponible**, documente el
  análisis y proponga una excepción con `id`, `herramienta`, `componente`, `justificacion`,
  `aprobado_por`, `creado` y `vence` (máximo 90 días).
* **MEDIUM:** corrija si el costo es bajo; si no, regístrelo con fecha de compromiso.
* **Secreto detectado:** no lo borre en silencio. Informe, rote la credencial y después
  limpie el historial.
* **Falso positivo:** justifíquelo con evidencia concreta en la excepción, **nunca editando
  la configuración del escáner para silenciar la regla completa**. La excepción a esto son
  los patrones de exclusión de directorios que nunca deben analizarse (`.venv`,
  `node_modules`), que no ocultan hallazgos del proyecto sino de sus dependencias.

Documentación del estándar: `~/SeguridadGeneral/00-gobernanza/` (política, convenciones,
flujo git, modos y aprobaciones), `01-seguridad/` (secretos, OIDC, hardening, checklist de
pase a producción, rollback) y `02-pipelines/` (workflows y configuración de escáneres).

Subagentes en `.claude/agents/`: `devsecops`, `seguridad` (solo lectura), `deploy` (no puede
desplegar a producción) y `proyectos` (solo lectura). Skills: `/aplicar-estandar-devsecops` y
`/pase-a-produccion`.

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
9. ¿`./security-local.sh` termina sin CRITICAL ni HIGH no exceptuados, con las cinco
   herramientas disponibles?

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
