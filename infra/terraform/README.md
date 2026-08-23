# Infraestructura AWS · FENC-PY

## Estructura

```
infra/terraform/
├── modules/                    Módulos reutilizables, sin provider ni backend propio
│   ├── kms-intermediate-ca/    Clave asimétrica de la CA subordinada (HSM FIPS 140-2 N3)
│   ├── audit-trail-dynamodb/   Pista de auditoría single-table + auditoría del panel
│   ├── evidence-vault-s3/      Bóvedas de firmados y de evidencias (Object Lock COMPLIANCE)
│   ├── signer-service/         ECS Fargate, IAM de mínimo privilegio, autoescalado
│   ├── api-edge/               WAF + API Gateway + VPC Link + Cognito con MFA
│   ├── crl-distribution/       S3 + CloudFront + Lambda + EventBridge (CRL diaria)
│   └── observability/          CloudTrail validado, GuardDuty, alarmas de kms:Sign
└── envs/
    ├── dev/                    Composición del entorno de desarrollo
    └── prod/                   Composición del entorno productivo
```

## Puesta en marcha

```bash
# 1. Estado remoto (una sola vez, en la cuenta de gestión)
./../../scripts/bootstrap-tfstate.sh

# 2. Parámetros del entorno
cd envs/dev
cp terraform.tfvars.example terraform.tfvars
cp backend.hcl.example backend.hcl
$EDITOR terraform.tfvars backend.hcl

# 3. Despliegue
terraform init -backend-config=backend.hcl
terraform plan -out=tfplan
terraform apply tfplan
```

## Decisiones y advertencias operativas

1. **Object Lock solo se habilita al crear el bucket.** Revise
   `object_lock_retention_days` antes del primer `apply`: en modo COMPLIANCE la
   retención es irreversible incluso para el usuario raíz de la cuenta. Un valor
   equivocado obliga a mantener el bucket hasta el vencimiento.
2. **Las claves asimétricas de KMS no rotan automáticamente.** La rotación de la CA
   intermedia es un procedimiento manual documentado (`docs/RUNBOOK-break-glass.md §5`).
   `enable_key_rotation` solo aplica a la clave simétrica de datos.
3. **Dos claves KMS distintas por diseño:** la de la CA (`SIGN_VERIFY`, sin permisos de
   cifrado) y la de datos (`ENCRYPT_DECRYPT`, con rotación anual). Nunca deben unificarse:
   comprometer el cifrado en reposo no debe comprometer la autoridad de certificación.
4. **Ciclo de dependencias.** La política de la clave de la CA necesita el ARN del rol de
   la tarea, y la tarea necesita el ARN de la clave. Se rompe construyendo el ARN del rol
   a partir de su nombre determinista en `locals`.
5. **La red es preexistente.** El stack consume `vpc_id` y `private_subnet_ids`. Se
   recomienda incorporar VPC Endpoints (`kms`, `s3`, `dynamodb`, `secretsmanager`, `logs`)
   para que el tráfico del signer no salga a Internet salvo hacia la TSA.
6. **`terraform apply` en producción requiere dos aprobaciones** y se ejecuta desde el
   pipeline con rol OIDC, nunca con credenciales estáticas.

## Verificación posterior al despliegue

```bash
# La clave de la CA no debe permitir cifrado
aws kms describe-key --key-id alias/pscnc-paraguay-intermediate-ca-dev \
  --query 'KeyMetadata.[KeyUsage,CustomerMasterKeySpec,Origin]'

# La bóveda de evidencias debe reportar modo COMPLIANCE
aws s3api get-object-lock-configuration --bucket pscnc-py-evidence-trail-dev

# CloudTrail con validación de integridad activa
aws cloudtrail describe-trails --query 'trailList[].[Name,LogFileValidationEnabled]'
```
