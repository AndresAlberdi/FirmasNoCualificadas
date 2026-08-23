# Entorno `prod`

Este directorio se compone deliberadamente **a partir de `envs/dev`** para evitar la
divergencia silenciosa entre entornos. El procedimiento de alta es explícito y revisado:

```bash
cp ../dev/{main.tf,variables.tf,outputs.tf,backend.tf} .
cp ../dev/terraform.tfvars.example terraform.tfvars
cp ../dev/backend.hcl.example backend.hcl
```

Y a continuación aplique **obligatoriamente** los siguientes ajustes antes del primer
`plan`:

| Ajuste | Valor en `prod` | Motivo |
| :-- | :-- | :-- |
| `locals.environment` | `"prod"` | Nombres, alias y etiquetas |
| `backend.tf` → `key` | `fenc-py/prod/terraform.tfstate` | Estado separado por entorno |
| `aws_lb.internal.enable_deletion_protection` | `true` | Evitar destrucción accidental |
| `module.signer_service.desired_count` | `≥ 2` | Alta disponibilidad multi-AZ |
| `module.signer_service.max_capacity` | Según proyección de carga | Autoescalado |
| `container_image` | Referencia **por digest** (`@sha256:…`) | Inmutabilidad del artefacto desplegado |
| `object_lock_retention_days` | Valor definitivo aprobado por Legal | Irreversible una vez escrito |
| `secops_admin_role_arns` | Roles productivos, con MFA obligatoria | Separación de funciones |
| Cuenta de AWS | Cuenta dedicada, distinta de `dev` | Aislamiento de radio de impacto |

Reglas adicionales del entorno productivo:

* `apply` únicamente desde el pipeline, con rol OIDC y dos aprobaciones registradas.
* Ningún recurso se modifica manualmente desde la consola; toda desviación detectada por
  `terraform plan` en el pipeline diario es un incidente de control de cambios.
* Todo cambio que altere algoritmos, perfiles de certificado o custodia de claves exige la
  actualización previa de la DPSC presentada ante la DGFDCE.
