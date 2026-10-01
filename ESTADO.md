# Estado del repositorio frente al estándar DevSecOps

Última actualización: 2026-10-01 (reusable 2.7 y acciones del #75 en `main`).

## Versión del estándar

**Reusable de seguridad 2.7** (job nuevo `workflows`: Checkov sobre `.github/workflows`, siempre), **`_reusable-dast.yml` 2.2** y los ajustes de `ci-multicloud.yml` de la plantilla 2.4. Camino: 2.6 en el PR #77 (`28ecea7`), DAST 2.2 y plantilla 2.4 en el PR #78 (`a9c7163`), 2.7 en el PR #79 (`6d82790`). Modo A, stack `multicloud`, componentes `signer`, `infra`, `dashboard` y `sdk`.

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
- **PR #79 (reusable 2.7).** Run 36828080492 sobre `7eb35ec`: 39 jobs en success, 0 fallidos, 11 omitidos; `compuerta-pr` en success; la base era `main` en `a9c7163`. El job nuevo `Workflows (Checkov)` pasó en los cuatro componentes y reportó «Checkov analizó 6 de 6 workflows; 0 hallazgo(s)», con `CKV_GHA_7` exceptuado. Fusionado el 2026-10-01 07:11 UTC en `6d82790`.
- **Primer run en `main` con el reusable 2.7.** Run 36828896081 sobre `6d82790`: success, 32 jobs en success de 43 (el resto omitidos); sin Environments. Code Scanning recibió las categorías `checkov-workflows-<componente>` con 0 resultados y no hubo alertas nuevas; las 18 abiertas son todas de Scorecard.
- **Code Scanning y `nosemgrep`.** Con el reusable 2.3 o posterior, un `nosemgrep` filtra el hallazgo del SARIF en vez de reabrir la alerta. Las alertas #75, #76 y #77 (Semgrep, `infra-terraform`) pasaron a `fixed` el 2026-10-01 05:58 UTC, con el análisis de `28ecea7` en 0 resultados, y no a `dismissed`.
- **Checkov sobre los workflows.** Hasta el reusable 2.6, el job `iac` analizaba solo el directorio de cada componente y nunca `.github/workflows/`; `CKV_GHA_7` solo aparecía en `./security-local.sh`. Desde el 2.7, el job `workflows` los analiza siempre. Medido con Checkov 3.3.13 (la versión que fija el job): analiza los 6 de 6 workflows, ninguno descartado en silencio, y marca `CKV_GHA_7` en `release.yml` (`tipo`, `prerelease`) y en `ci-multicloud.yml` (`tag`, `confirmar`). Está exceptuado en `.devsecops.yml` hasta el 2026-12-30 (90 días); la justificación cubre los dos archivos y se verificó contra su código: `confirmar` solo se compara con `DESPLEGAR` en condiciones `if:`, y `tag` llega a `ref:` de `actions/checkout` y a la variable `TAG`, que el shell usa entre comillas tras exigir tag existente, sin guion y ancestro de `main`.
- **PR #81 (concurrency).** Fusionado el 2026-10-01 en `8abaf59`: el `group` de `ci-multicloud.yml` usa `github.run_id` y no `github.sha`, para que un tag y un `workflow_dispatch` sobre el mismo commit no se cancelen entre sí.
- **Dependabot #75 (grupo `actions-minor-patch`, 8 acciones).** Revisado el diff completo: solo cambian pines por SHA en 5 workflows. Los 7 SHAs de tags se verificaron contra el repositorio de cada acción; el de `checkov-action` es un commit de `master` sin tag. Head `c75c080`, al día con `main` en `8abaf59`, 39 checks en success y 11 omitidos. Aprobado por el agente con AndresAlberdi por delegación y fusionado con segurolotengopy, por squash, el 2026-10-01 en `20d06d2`, con el OK de Andres en el chat.
- **`./security-local.sh`:** CRITICAL=0, HIGH=0, APROBADO.

## Pendiente

- **Excepción `CKV_GHA_7`:** revisar antes del 2026-12-30; si los inputs ya no hacen falta, quitarlos de `release.yml` y de `ci-multicloud.yml` y borrar la excepción.
- **Categorías viejas de Code Scanning** (`semgrep`, `trivy-fs`, `trivy-config`, sin análisis desde el 2026-09-12): decisión de Andres, 2026-10-01, **dejarlas como están**. Eran 1.335 análisis con 755, 362 y 36 resultados. Se borraron 248 antes de que el clasificador del modo automático bloqueara un `DELETE`; quedan unos 1.077 con unos 988 resultados de historial, y GitHub podó unos 10 por su cuenta. No estorban: ninguna de las 34 alertas del repositorio, en ningún estado, tiene su instancia más reciente en esas categorías, y no reciben análisis nuevos. Borrar el resto es irreversible y no aporta nada funcional. Al borrar, GitHub exige `confirm_delete` para el último análisis de cada conjunto («puede perder datos históricos de alertas»).
- **Primer run en `main` con las acciones del #75:** el run de CI/CD Multicloud sobre `20d06d2` no se había medido al escribir esto. Mirar `iac` y `workflows`: el pin de `checkov-action` trae Checkov 3.3.19 y este documento midió con la 3.3.13. Si pasa limpio, borrar este punto.
- **Comentario del pin de `checkov-action`** en `_reusable-security.yml`: sigue diciendo «master @ 2026-08-26» y el pin vigente es de `master` del 2026-09-17 (commit `444c9db`). Dependabot no lo actualiza; corregirlo en la próxima actualización del estándar.
- **`gitleaks.toml` 2.1** del estándar (allowlist de `.trivy-cache/`, `.security-reports/` y `.deploy-log/`): nuestra copia es idéntica a la versión anterior, sin cambios propios; se trae en la próxima actualización, por fusión de tres vías.

## Cómo se actualiza

El procedimiento es `Prompts/actualizar-repo-al-estandar.md` de SeguridadGeneral. Un PR por bloque, fusión con OK de Andres, CI verde sobre lo que se fusiona y sin `--admin`.
