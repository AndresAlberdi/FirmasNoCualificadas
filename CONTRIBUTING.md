# Guía de Contribución

## Flujo de trabajo

* Ramas: `main` (protegida, siempre desplegable), `develop` (integración),
  `feat/*`, `fix/*`, `chore/*`, `docs/*`.
* Commits en formato [Conventional Commits](https://www.conventionalcommits.org/):
  `feat(crypto): emitir certificado efímero con OID de política`.
* Todo pull request requiere: CI en verde, una aprobación como mínimo y **dos aprobaciones**
  si toca `services/src/pscnc/crypto/`, `infra/terraform/modules/kms-intermediate-ca/` o
  `infra/terraform/modules/evidence-vault-s3/`.

## Antes de abrir un PR

```bash
make lint
make test
make tf-fmt
```

## Reglas que bloquean la fusión

1. Datos personales reales, cédulas verdaderas o PDFs de clientes en fixtures de prueba.
   Use el generador de datos sintéticos de `services/tests/conftest.py`.
2. Secretos, claves privadas o ARNs de cuentas productivas en el código o en los tests.
3. Cambios en el perfil del certificado o en los algoritmos criptográficos sin la
   actualización correspondiente de la DPSC y del ADR-0004.
4. Nuevas rutas de la API sin control de tenant explícito (ADR-0005).
5. Dependencias sin versión acotada o con vulnerabilidades conocidas de severidad alta.

## Estilo

* Python: `ruff` (formato y lint) y `mypy` en modo estricto sobre `services/src`.
  Tipado obligatorio en las firmas públicas. Docstrings en español.
* TypeScript: `eslint` + `prettier`, componentes funcionales y tipado explícito de props.
* Terraform: `terraform fmt`, un módulo por dominio, sin `provider` ni `backend` dentro de
  los módulos, variables con `description` y `type` siempre presentes.
* Mensajes de log en inglés técnico; documentación y comentarios de dominio en español.
