# Estado del repositorio frente al estándar DevSecOps

Última actualización: 2026-09-30.

## Versión del estándar

**Reusable de seguridad 2.6** (SeguridadGeneral, `origin/main` en 1460e28 al momento de actualizar). Modo A, stack `multicloud`, componentes `signer`, `infra`, `dashboard` y `sdk`.

| Archivo | Origen | Cambios propios que se conservan |
| :-- | :-- | :-- |
| `.github/workflows/_reusable-security.yml` | 2.6 | pip-audit sobre el `uv.lock` exportado; paso «Detalle legible de los hallazgos de Trivy config» |
| `.github/workflows/codeql.yml` | 2.1 | sin filtro de rama base y con `edited` en `types` |
| `.github/trivy.yaml` | 2.1 | `severity` con su comentario medido; exclusiones `**/` (monorepo), `**/.security-reports` y `**/.claude/worktrees` |
| `.github/workflows/_reusable-dast.yml`, `.github/zap-rules.tsv` | 2.1 | ninguno |
| `.github/semgrep.yml` | 2.1 | ninguno |
| `deploy.sh`, `security-local.sh` | vigentes | ninguno |
| `.pre-commit-config.yaml` | propio | configuración propia, anterior a la plantilla; no se actualiza (decisión de Andres, 2026-09-30) |

`ci-multicloud.yml` y `dependabot.yml` son del repositorio. El único ajuste exigido por el reusable 2.6 fue conceder `pull-requests: read` en el job `seguridad-estatica`.

## Lo que se midió

- **Dependencias.** Antes de subir el estándar, el análisis local marcó 29 HIGH (`brace-expansion`, `undici`, `urllib3`) por avisos publicados después del último run verde de `main`. Se corrigieron en el PR #76 (solo lockfiles), fusionado el 2026-10-01 02:06 UTC.
- **Primer run en `main` tras #76:** run 36804294956 sobre `6dbe186`, success. El run anterior era 35546354045 sobre `d702f09`.
- **Environments:** el repositorio no tiene ninguno (la consulta a la API no devuelve nombres); no se creó ninguno por la actualización.
- **Checkov en CI** analiza solo el directorio de cada componente, nunca `.github/workflows/`. Por eso `CKV_GHA_7` sobre `release.yml` aparece en `./security-local.sh` (que analiza todo el repositorio) y no en CI.

## Pendiente

- **Run que prueba el estándar 2.6:** se registra en el PR de la actualización y aquí, en un PR de documentación posterior, cuando exista el primer run en `main` con el reusable 2.6.
- **Code Scanning.** Con el reusable 2.3 o posterior, un `nosemgrep` ya no reabre la alerta (se filtra del SARIF). Debería cerrar las alertas #75 a #77; falta confirmarlo en el primer run en `main`. Con las categorías por componente quedan categorías viejas: antes de borrar una hay que sumar `results_count` de todo su historial, y borrar historial con resultados necesita OK aparte.
- **`CKV_GHA_7`:** decidir entre una excepción con vencimiento de 90 días en `.devsecops.yml` o quitar los dos inputs de `release.yml`. Decisión de Andres.
- **Dependabot #75** (10 acciones) toca los mismos workflows que se actualizan; tendrá que rebasar tras la fusión.

## Cómo se actualiza

El procedimiento es `Prompts/actualizar-repo-al-estandar.md` de SeguridadGeneral. Un PR por bloque, fusión con OK de Andres, CI verde sobre lo que se fusiona y sin `--admin`.
