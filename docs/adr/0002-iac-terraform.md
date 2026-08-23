# ADR-0002 · Infraestructura como código con Terraform

* **Estado:** Aceptado
* **Fecha:** 2026-08-23
* **Decisores:** Arquitectura, DevOps

## Contexto

Toda la infraestructura reside en AWS y debe ser auditable: la DGFDCE puede requerir
evidencia de los controles técnicos declarados en la DPSC. Se necesita que el estado de la
infraestructura sea reproducible, revisable en pull request y comparable en el tiempo.

## Decisión

Se adopta **Terraform ≥ 1.9** con módulos por dominio y composición por entorno
(`envs/dev`, `envs/prod`). El estado remoto se guarda en S3 con versionado y bloqueo en
DynamoDB, dentro de una cuenta de gestión separada de las cuentas de carga de trabajo.

## Justificación

1. El `terraform plan` publicado en el pull request es, en sí mismo, evidencia de control
   de cambios ante una auditoría regulatoria.
2. Los documentos de diseño ya expresan los recursos en el vocabulario de Terraform
   (`aws_kms_key`, `aws_iam_role`), lo que reduce la traducción y el riesgo de desviación.
3. La portabilidad del lenguaje permite incorporar proveedores no-AWS (TSA, DNS, alertas)
   bajo el mismo flujo de trabajo.
4. CDK ofrece mejor ergonomía en ECS, pero introduce una capa de síntesis que dificulta la
   revisión línea a línea del recurso final, precisamente lo que la auditoría exige.

## Consecuencias

* Separación estricta entre módulos (sin `provider` propio, sin `backend`) y entornos.
* Los valores sensibles (ARNs de cuenta, dominios, contactos regulatorios) se pasan por
  `*.tfvars` fuera del repositorio; solo se versionan los `*.tfvars.example`.
* El pipeline ejecuta `fmt`, `validate`, `checkov` y `plan`; el `apply` es manual con
  aprobación de dos personas en el entorno `prod`.
