# Orden de fusión de los PR abiertos — foto del 2026-09-11

> **Esto es una foto, no una regla.** Describe los PR abiertos al 2026-09-11, todos creados
> sobre `main` en `e43c1b9`. Cada fusión cambia `main`, así que antes de fusionar el siguiente
> hay que repetir la comprobación de conflictos:
>
> ```bash
> git fetch origin
> git merge-tree --write-tree --name-only origin/main origin/<rama-del-pr>
> ```
>
> Sale con 0 si no hay conflictos; si los hay, lista los archivos. Cuando todos los PR de esta
> lista estén fusionados o cerrados, este documento queda solo como registro.

El ruleset de `main` exige squash, el check `compuerta-pr` y la rama **al día**
(`strict_required_status_checks_policy: true`). En la práctica, después de cada fusión el PR
siguiente necesita «Update branch» y una vuelta más de CI antes de poder fusionarse.

## 1. Qué hay abierto

| PR | Rama | Qué hace | CI | Revisión |
| :-- | :-- | :-- | :-- | :-- |
| #45 | `dependabot/github_actions/…` | Actualiza cuatro acciones de GitHub | Verde | Pendiente |
| #46 | `fix/crypto-entorno-obligatorio-ca-efimera` | La CA efímera exige el entorno | Verde | Pendiente — **duplica al #48** |
| #47 | `fix/bloque-constancia-legible` | El bloque visible de constancia se lee y lleva la marca de entorno | Verde | Pendiente |
| #48 | `fix/ca-efimera-hereda-entorno` | La CA efímera exige el entorno | Verde | Pendiente — **duplica al #46** |
| #49 | `fix/sca-por-componente` | `security-local.sh` analiza las dependencias de `services`, `dashboard` y `sdk` | Verde | **Aprobado** |
| #50 | `chore/script-firma-prueba-alianza` | Script de firma de prueba para la firma cualificada posterior | Verde | Pendiente |
| #51 | `ci/trivy-alinear-plantilla` | Escáneres inválidos y clave obsoleta en `.github/trivy.yaml` | Verde | Pendiente |
| #52 | `fix/acta-hereda-entorno` | El acta y el servicio de transacciones exigen el entorno | Verde | Pendiente |
| — | `fix/qualified-flujo-legado` (local, sin publicar) | El flujo heredado deja de declarar cualificado un sello de prueba | — | Sin PR |

## 2. Conflictos comprobados

Comprobados con `git merge-tree` entre todos los pares. Los pares que no figuran se fusionan sin
conflictos.

| Par | Archivo | Cómo se resuelve |
| :-- | :-- | :-- |
| #46 + #48 | `ephemeral_ca.py` | No se resuelve: son el mismo arreglo. Se fusiona uno y se cierra el otro (§3) |
| #46 + #47, #47 + #48 | `tests/test_constancia_visible.py` | Queda la versión del #47. Su fixture `fabrica_de_firmantes` ya pasa `environment=entorno`; se descarta la línea `environment="prod"` que #46/#48 agregan al fixture anterior |
| #46 + `fix/qualified-flujo-legado` | `dependencies.py`, `tests/test_dependencias.py` | Desaparece al cerrar #46 |
| #48 + `fix/qualified-flujo-legado` | `dependencies.py` | Desaparece al sacar de la rama el commit `3ca1833`, que repite el arreglo del #48 (no comprobado después de sacarlo) |
| #47 + #50 | `docs/PENDIENTES.md` | Ver el choque de identificadores más abajo |

**Choque de identificadores en `docs/PENDIENTES.md`.** Git no lo marca como conflicto, pero es
un error. En `main` el último pendiente técnico es T-20, y **tres ramas agregan un T-21 distinto**:

| Rama | Filas nuevas |
| :-- | :-- |
| #47 | T-21 — datos del tenant con caracteres que la fuente del bloque no codifica |
| `fix/qualified-flujo-legado` | T-21 — la respuesta heredada no declara si el sello es cualificado |
| #50 | T-21, T-22 y T-23 — hoja de firma, compensaciones del script y resultado con Alianza |

El primero que se fusione conserva su número y los siguientes renumeran al siguiente libre al
actualizar su rama. Hay que buscar también las referencias al número viejo en el resto del
repositorio.

## 3. Decisión pendiente: #46 o #48

Hacen **el mismo cambio de código**: `environment` pasa a ser obligatorio en
`EphemeralCertificateAuthority` y `build_signing_service` lo recibe de la configuración. Solo
difieren en las pruebas:

- **#46** arma el servicio en `dev`, emite un certificado y comprueba que su OU empiece con
  `[NO VALIDO - ENTORNO DEV]`. Prueba el resultado final.
- **#48** comprueba que la autoridad reciba el entorno de la configuración, en `dev`, `staging`
  y `prod`.

**Recomendación:** fusionar el #48 y cerrar el #46, pasando antes al #48 la prueba del
certificado del #46. El #52 y la rama `fix/qualified-flujo-legado` se armaron contra el #48.

## 4. Orden propuesto

1. **#49.** Ya está aprobado y solo toca `security-local.sh`.
2. **#51.** Solo toca `.github/trivy.yaml`.
3. **#45.** Solo toca workflows. Quien lo revise tiene que verificar cada SHA nuevo contra el
   repositorio de la acción (regla 8 del estándar en `CLAUDE.md`).
4. **#48**, después de decidir el §3. Se cierra el #46.
5. **#47.** Resolver `test_constancia_visible.py` como indica el §2. Su T-21 queda.
6. **#52.** No tiene conflictos con ninguno.
7. **`fix/qualified-flujo-legado`.** Sacar `3ca1833`, renumerar su T-21, correr `make test` y
   abrir el PR.
8. **#50**, al final. Renumerar sus tres filas y revisar su T-22, que dice que el bloque del #22
   sale ilegible: con el #47 fusionado deja de ser cierto y probablemente sobre.

Solo los pasos 4 y 7 cambian el comportamiento de firma. El resto son CI, herramientas o
documentación.
