# Estado del repositorio frente al estándar DevSecOps

Última actualización: 2026-10-01 (reusable 2.7).

## Versión del estándar

**Reusable de seguridad 2.7** (job nuevo `workflows`: Checkov sobre `.github/workflows`, siempre), **`_reusable-dast.yml` 2.2** y los ajustes de `ci-multicloud.yml` de la plantilla 2.4. Camino: 2.6 en el PR #77 (`28ecea7`), DAST 2.2 y plantilla 2.4 en el PR #78 (`a9c7163`), 2.7 en el tercer PR de la actualización. Modo A, stack `multicloud`, componentes `signer`, `infra`, `dashboard` y `sdk`.

| Archivo | Origen | Cambios propios que se conservan |
| :-- | :-- | :-- |
| `.github/workflows/_reusable-security.yml` | 2.7 | pip-audit sobre el `uv.lock` exportado; paso «Detalle legible de los hallazgos de Trivy config» |
| `.github/workflows/codeql.yml` | 2.1 | sin filtro de rama base y con `edited` en `types` |
| `.github/trivy.yaml` | 2.1 | `severity` con su comentario medido; exclusiones `**/` (monorepo), `**/.security-reports` y `**/.claude/worktrees` |
| `.github/workflows/_reusable-dast.yml` | 2.2 | ninguno |
| `.github/zap-rules.tsv`, `.github/semgrep.yml` | 2.1 | ninguno |
| `deploy.sh`, `security-local.sh` | vigentes | ninguno |
| `.pre-commit-config.yaml` | propio | configuración propia, anterior a la plantilla; no se actualiza (decisión de Andres, 2026-09-30) |

`ci-multicloud.yml` y `dependabot.yml` son del repositorio. Ajustes que le exige el estándar: `pull-requests: read` en `seguridad-estatica` (reusable 2.6); `concurrency` con la condición en `group` y `cancel-in-progress: true`, porque Checkov descarta en silencio los workflows con una expresión en `cancel-in-progress`; y `HEALTH_PATH` por defecto `/health` (Cloud Run reserva las rutas que terminan en «z»). Este repositorio no despliega (`produccion: false`, servicio destinado a ECS) y no define la variable `HEALTH_PATH`.

## Lo que se midió

- **Dependencias.** Antes de subir el estándar, el análisis local marcó 29 HIGH (`brace-expansion`, `undici`, `urllib3`) por avisos publicados después del último run verde de `main`. Se corrigieron en el PR #76 (solo lockfiles), fusionado el 2026-10-01 en `6dbe186`.
- **PR #77 (estándar 2.6).** Run 36805151909 sobre `522ca0d`: 35 jobs en success, 0 fallidos, 11 omitidos; `compuerta-pr` en success; la base era `main` en `6dbe186`.
- **PR #78 (DAST 2.2, plantilla 2.4 y excepción de `CKV_GHA_7`).** Run 36822562498 sobre `bee6622`: 35 jobs en success, 0 fallidos, 11 omitidos; `compuerta-pr` en success; la base era `main` en `28ecea7`. Fusionado el 2026-10-01 06:51 UTC en `a9c7163`.
- **Primer run en `main` con el reusable 2.6.** Run 36822291031 sobre `28ecea7`: success, 28 jobs en success y el resto omitidos. No se creó ningún Environment (la API devuelve la lista vacía).
- **Run en `main` tras #78.** Run 36827019985 sobre `a9c7163`: success, 28 jobs en success y el resto omitidos; sin Environments nuevos.
- **Code Scanning y `nosemgrep`.** Con el reusable 2.3 o posterior, un `nosemgrep` filtra el hallazgo del SARIF en vez de reabrir la alerta. Las alertas #75, #76 y #77 (Semgrep, `infra-terraform`) pasaron a `fixed` el 2026-10-01 05:58 UTC, con el análisis de `28ecea7` en 0 resultados, y no a `dismissed`.
- **Checkov sobre los workflows.** Hasta el reusable 2.6, el job `iac` analizaba solo el directorio de cada componente y nunca `.github/workflows/`; `CKV_GHA_7` solo aparecía en `./security-local.sh`. Desde el 2.7, el job `workflows` los analiza siempre. Medido con Checkov 3.3.13 (la versión que fija el job): analiza los 6 de 6 workflows, ninguno descartado en silencio, y marca `CKV_GHA_7` en `release.yml` (`tipo`, `prerelease`) y en `ci-multicloud.yml` (`tag`, `confirmar`). Está exceptuado en `.devsecops.yml` hasta el 2026-12-30 (90 días); la justificación cubre los dos archivos y se verificó contra su código: `confirmar` solo se compara con `DESPLEGAR` en condiciones `if:`, y `tag` llega a `ref:` de `actions/checkout` y a la variable `TAG`, que el shell usa entre comillas tras exigir tag existente, sin guion y ancestro de `main`.
- **`./security-local.sh`:** CRITICAL=0, HIGH=0, APROBADO.

## Pendiente

- **Excepción `CKV_GHA_7`:** revisar antes del 2026-12-30; si los inputs ya no hacen falta, quitarlos de `release.yml` y de `ci-multicloud.yml` y borrar la excepción.
- **Categorías viejas de Code Scanning** (`semgrep`, `trivy-fs`, `trivy-config`, sin análisis desde el 2026-09-12). Suman 761, 362 y 36 resultados en su historial, así que borrarlas necesita autorización aparte de Andres; mientras tanto no estorban.
- **Dependabot #75** (10 acciones) toca los mismos workflows que se actualizaron y tendrá que rebasar.
- **Run del PR del 2.7:** se registra en su descripción y, tras fusionarlo, en un PR de documentación (un archivo no puede citar el run de su propio commit).

## Cómo se actualiza

El procedimiento es `Prompts/actualizar-repo-al-estandar.md` de SeguridadGeneral. Un PR por bloque, fusión con OK de Andres, CI verde sobre lo que se fusiona y sin `--admin`.
