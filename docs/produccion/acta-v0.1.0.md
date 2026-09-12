# Acta de pase a producción — firmasnocualificadas — v0.1.0 — 2026-09-11

| Campo | Valor |
|---|---|
| Proyecto | `firmasnocualificadas` (según `.devsecops.yml`) |
| Versión propuesta | **v0.1.0** (commit `e43c1b9`, HEAD de `origin/main`) |
| Modo de operación | A (repositorio público) |
| Tipo de pase | Primer pase: nunca se creó un tag |
| Componentes desplegables | **Ninguno.** Los cuatro (`signer`, `infra`, `dashboard`, `sdk`) declaran `proveedor: ninguno`, y el manifiesto `produccion: false` |
| Run del pipeline | [33999840619](https://github.com/AndresAlberdi/FirmasNoCualificadas/actions/runs/33999840619), `push` a `main`, 2026-09-05, en verde |
| Preparado por | Claude Code (skill `pase-a-produccion`) |
| Aprueba | Propietario (pendiente) |

## Decisión propuesta

**RECHAZADO como pase a producción.** No debe procederse hasta resolver los puntos de la última
sección, aunque los comandos del tag estén preparados más abajo. Hay tres motivos:

1. **No hay nada que desplegar.** `desplegar-produccion` exige
   `needs.preparar.outputs.hay_desplegables == 'true'`, y ningún componente tiene proveedor.
   Además, el ADR-0011 fija que **FNC entrega el motor y el cliente lo opera**: la producción
   ocurre en la cuenta del cliente, no en la de FNC (`docs/DESPLIEGUE-DEL-CLIENTE.md`). Lo único
   que FNC puede «pasar» es una **versión del motor**: tag y GitHub Release.
2. **SEC-06 está en rojo, y es bloqueante.** El escaneo de secretos y la protección de push
   están desactivados en un repositorio público de modo A.
3. **No existe el Environment `production`.** El modo A lo exige, con al menos un revisor
   humano; sin él no queda registrada ninguna aprobación humana.

Aunque se resolvieran esos tres, **el nivel 2 no puede ofrecerse en producción** mientras
sigan abiertos los bloqueantes de `docs/PENDIENTES.md` §1 (ADR-0007).

## Versión propuesta y por qué

No hay ningún tag. `release.yml` toma `v0.0.0` como base, analiza todo el historial y, como
hay commits `feat`, incrementa la minor: **v0.1.0**. Se mantiene por debajo de 1.0 porque el
producto todavía no puede operarse en producción.

## Cambios incluidos (historial completo hasta `e43c1b9`)

- **feat:** la jurisdicción como configuración (ADR-0008); claves de KMS por inquilino y
  compuerta de conservación; actas selladas en JWS verificables por terceros; contrato público
  v1 con OpenAPI, idempotencia y SDK de TypeScript; nivel 2 con PAdES, sello de tiempo y marca
  de entorno; persistencia en DynamoDB; verificación pública del acta en el navegador y contra
  la API real; nombre y apellido del firmante por separado; despliegue en la cuenta del
  cliente; bloque visible de constancia en el PDF.
- **fix:** autenticación de peticiones multipart; hallazgos bloqueantes del primer escaneo;
  pypdf 6.16.2; egreso del servicio de firma restringido por destino; extensiones y sujeto del
  certificado conforme al DOC-ICPP-20 v2.0; configuración de Dependabot.

**Sin incluir:** los PR abiertos al 2026-09-11. Tres corrigen defectos que v0.1.0 **sí
llevaría**: el bloque visible ilegible (#47), los certificados sin marca de entorno del flujo
heredado (#46/#48) y las actas que asumen `prod` (#52). Ver
`docs/produccion/orden-de-fusion-2026-09-11.md`.

## Checklist (`SeguridadGeneral/01-seguridad/05-checklist-pase-a-produccion.md` v2.0)

Los estados son `Verde`, `Rojo`, `N/A` (con justificación) o `No verificado`. Lo que no pudo
verificarse no figura en verde.

### 1. Repositorio y Git

| ID | Nivel | Estado | Evidencia |
|---|---|---|---|
| REP-01 | B | Verde | Job `preparar (leer .devsecops.yml)` en verde en el run 33999840619. `check-jsonschema` no se ejecutó en local |
| REP-02 | B | Verde | Ruleset `proteccion-main`: `enforcement=active`, sin actores con bypass; reglas `pull_request`, `required_linear_history`, `non_fast_forward`, `deletion` y `required_status_checks` con `compuerta-pr` y `strict=true` |
| REP-03 | B | Verde | `required_approving_review_count=1` |
| REP-04 | B | Verde | `.github/CODEOWNERS` asigna `*` a `@segurolotengopy`, lo que cubre `.github/`, `infra/` y `.devsecops.yml`. El ruleset no exige revisión de code owners (`require_code_owner_review=false`) |
| REP-05 | B | Verde | `gitleaks detect --source .` (modo git, recorre el historial) desde `security-local.sh` el 2026-09-11, sin hallazgos |
| REP-06 | B | Verde | `git ls-files` no contiene `.env`, claves ni certificados. El único `*.auto.tfvars` versionado lo genera `make tf-jurisdiccion` desde el perfil y no contiene secretos |
| REP-07 | R | Verde | El ruleset solo admite squash; el historial usa Conventional Commits |
| REP-08 | B | Pendiente | El tag no existe. `TAG_FIRMADO_REQUERIDO=false`, así que lo crea `release.yml` |
| REP-09 | B | Verde | `.github/dependabot.yml`: github-actions, npm (`dashboard` y `sdk`), uv, docker y terraform |
| REP-10 | R | N/A | Solo aplica al modo B |

### 2. Pipeline

| ID | Nivel | Estado | Evidencia |
|---|---|---|---|
| PIP-01 | B | Pendiente | No hay run sobre un tag. El último run en `main` está en verde; `construir`, `desplegar-*` y `dast-y-humo` se omiten porque no hay nada desplegable |
| PIP-02 | B | Verde | Todas las líneas `uses:` de `.github/workflows/*.yml` están fijadas por un SHA de 40 caracteres |
| PIP-03 | B | Verde | `permissions: contents: read` a nivel de workflow en todos, salvo `scorecard.yml` con `read-all`, que es lo que exige Scorecard |
| PIP-04 | B | No verificado | Hay `concurrency` y `timeout-minutes`, pero no se contrastaron job por job |
| PIP-05 | B | Verde | `seguridad-estatica` en verde en los cuatro componentes. `security-local.sh` del 2026-09-11 (`.security-reports/20260911-194508`): CRITICAL=0, HIGH=0 |
| PIP-06 | B | Verde | Job `calidad` en verde en los cuatro componentes con `cobertura_minima: 70` |
| PIP-07, PIP-08 | B | N/A | No se construye ninguna imagen (`construir` se omite: ningún componente es desplegable) |
| PIP-09 | B | N/A | `seguridad.dast: false`, justificado en el manifiesto: no hay staging desplegado |
| PIP-10 | B | N/A | No hay identidad federada: FNC no despliega (ADR-0011) |
| PIP-11 | B | Verde | CodeQL activo; Code Scanning recibe análisis de CodeQL, Semgrep OSS y Trivy |
| PIP-12 | R | Verde | Scorecard 7.5 sobre `e43c1b9` (API pública, 2026-09-05) |
| PIP-14 | B | N/A | No hay `post-despliegue` porque no hay despliegue |

### 3. Secretos e identidad

| ID | Nivel | Estado | Evidencia |
|---|---|---|---|
| SEC-02 | B | Verde | `gh secret list`: el repositorio no tiene secretos, y por lo tanto ninguno prohibido |
| SEC-03 | B | Rojo / N/A | No existe el Environment `production`. N/A mientras FNC no despliegue; si alguna vez despliega, pasa a Rojo |
| SEC-06 | B | **Rojo** | `security_and_analysis`: `secret_scanning` y `secret_scanning_push_protection` en `disabled`. En un repositorio público son gratuitos |
| SEC-01, SEC-04, SEC-05, SEC-07 a SEC-11 | B/R | N/A | Sin despliegue ni secretos de aplicación en infraestructura de FNC. Los secretos de operación son del cliente (`docs/DESPLIEGUE-DEL-CLIENTE.md` §1) |

### 4. Nube, 6. Datos y 7. Operación

**N/A**, con la misma justificación: FNC no opera infraestructura de producción. Estos controles
los cumple el cliente en su cuenta, como parte de su propio pase.

### 5. Aplicación

No se hizo la revisión OWASP manual del checklist. Lo que aportan los controles automáticos del
pipeline (SAST, SCA, IaC) está en PIP-05 y PIP-11. **No verificado** como sección completa.

### Alertas abiertas

- **Dependabot high/critical:** 0.
- **Code Scanning:** 20 abiertas (13 medium, 3 high y 1 low entre las que tienen severidad). Las
  **3 high son de Scorecard y no del código**: `Maintained` (#58), `CodeReview` (#57) y
  `BranchProtection` (#42), creadas el 2026-09-02.
- **Secret scanning:** desactivado (ver SEC-06).
- **Issues `incidente` abiertos:** ninguno (la etiqueta no existe).

## Riesgos aceptados (excepciones vigentes en `.devsecops.yml`)

Veintisiete excepciones, **todas creadas el 2026-09-02 y con vencimiento el 2026-12-02**:
ninguna vencida y ninguna vence en los próximos 30 días. Todas corresponden al componente
`infra`: CloudFront de la CRL sin WAF (AWS-0011 y siete checks de checkov), replicación y
ciclo de vida de buckets, registro de acceso, autorizador de API Gateway, egreso a la TSA,
recuperación a un punto en el tiempo en la tabla de idempotencia, firma de código de la
función de la CRL, SNS de CloudTrail, GuardDuty parametrizado, políticas de clave, protección
contra borrado del balanceador y función de la CRL fuera de la VPC. La justificación completa
de cada una está en el manifiesto.

## Plan de rollback

**N/A para despliegue:** FNC no despliega. Para la versión del motor, un tag publicado **no se
reescribe**. Si v0.1.0 resulta defectuosa, se publica v0.1.1 con la corrección y se marca la
Release de v0.1.0 con la advertencia.

## Pendientes antes de aprobar

1. **Activar el escaneo de secretos y la protección de push** en Settings → Code security
   (SEC-06). Lo hace el propietario: es un cambio de configuración de seguridad de la cuenta.
2. **Decidir qué significa «producción» para este repositorio.** Con el ADR-0011, el pase de
   FNC es publicar una versión, no desplegar. Crear igual el Environment `production` con
   revisor, o registrar esa decisión en el manifiesto, es decisión del propietario.
3. **Fusionar antes del tag** los PR que corrigen defectos que v0.1.0 llevaría: #47, #48 (o
   #46) y #52. Si se fusionan, esta acta debe rehacerse sobre el nuevo HEAD.
4. Completar PIP-04 y la sección 5 (revisión OWASP) o registrar por qué no aplican.

## Comandos del tag (preparados, no ejecutados)

Solo después de resolver los pendientes. Con `TAG_FIRMADO_REQUERIDO=false`, la vía canónica
(REP-08) es que el tag lo cree `release.yml`, que además genera el CHANGELOG y la Release:

```bash
gh workflow run release.yml --ref main -f tipo=auto -f prerelease=false
```

No hay `RELEASE_TOKEN`, así que `release.yml` lanza `ci-multicloud.yml` sobre el tag por
`workflow_dispatch`. `desplegar-produccion` se omite de todas formas (`hay_desplegables`
es falso). **Esto publica una versión; no despliega nada.**

La alternativa manual, con firma, solo se justifica si se activa `TAG_FIRMADO_REQUERIDO`. La
clave SSH ya está configurada (`gpg.format=ssh`, `tag.gpgSign=true`). Así no se genera la
Release:

```bash
git checkout main && git pull --ff-only
git tag -s v0.1.0 -m "Release v0.1.0 — firmasnocualificadas"
git push origin v0.1.0
```

Claude Code no ejecuta ninguno de los dos.
