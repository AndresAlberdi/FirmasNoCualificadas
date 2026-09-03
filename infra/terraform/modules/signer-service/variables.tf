variable "resource_prefix" {
  description = <<-DESC
    Prefijo de los nombres de recursos. Lo fija quien despliega, y por defecto NO
    nombra a un prestador de servicios de confianza: el motor lo despliega el
    cliente en su propia cuenta para firmar sus propias contrataciones (ADR-0011),
    y un recurso llamado «pscnc-…» en su cuenta lo etiquetaría como prestador,
    que es justamente lo que el encuadre niega.
  DESC
  type        = string
  default     = "fenc"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,20}$", var.resource_prefix))
    error_message = "El prefijo debe ser minúsculas, dígitos y guiones, de 2 a 21 caracteres."
  }
}

variable "environment" {
  description = "Entorno lógico del despliegue."
  type        = string
}

variable "region" {
  description = "Región de AWS."
  type        = string
}

variable "account_id" {
  description = "Identificador de la cuenta de AWS."
  type        = string
}

variable "vpc_id" {
  description = "VPC donde corre el servicio."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subredes privadas sin ruta directa a Internet."
  type        = list(string)
}

variable "load_balancer_security_group_id" {
  description = "Security group del balanceador interno autorizado a alcanzar el servicio."
  type        = string
}

variable "target_group_arn" {
  description = "Target group del balanceador interno."
  type        = string
}

variable "container_image" {
  description = "Imagen del servicio de firma (ECR, con digest inmutable en producción)."
  type        = string
}

variable "container_port" {
  description = "Puerto de escucha de la aplicación."
  type        = number
  default     = 8080
}

variable "task_cpu" {
  description = "Unidades de CPU de la tarea Fargate."
  type        = string
  default     = "1024"
}

variable "task_memory" {
  description = "Memoria de la tarea Fargate en MiB."
  type        = string
  default     = "2048"
}

variable "desired_count" {
  description = "Cantidad mínima de tareas en ejecución."
  type        = number
  default     = 2
}

variable "max_capacity" {
  description = "Cantidad máxima de tareas bajo autoescalado."
  type        = number
  default     = 10
}

variable "kms_ca_key_arn" {
  description = "ARN de la clave KMS de la CA intermedia."
  type        = string
}

variable "kms_data_key_arn" {
  description = "ARN de la clave KMS de cifrado de datos (distinta de la CA)."
  type        = string
}

variable "audit_table_arn" {
  description = "ARN de la tabla de auditoría."
  type        = string
}

variable "audit_table_name" {
  description = "Nombre de la tabla de auditoría."
  type        = string
}

variable "signed_bucket_arn" {
  description = "ARN del bucket de documentos firmados."
  type        = string
}

variable "signed_bucket_name" {
  description = "Nombre del bucket de documentos firmados."
  type        = string
}

variable "evidence_bucket_arn" {
  description = "ARN del bucket WORM de evidencias."
  type        = string
}

variable "evidence_bucket_name" {
  description = "Nombre del bucket WORM de evidencias."
  type        = string
}

variable "secret_arns" {
  description = "ARNs de secretos que el servicio puede leer (HMAC B2B, credenciales de TSA y onboarding)."
  type        = list(string)
  default     = []
}

variable "container_secrets" {
  description = "Secretos inyectados como variables de entorno de la tarea."
  type = list(object({
    name       = string
    value_from = string
  }))
  default = []
}

variable "secops_topic_arn" {
  description = "Tópico SNS de alertas de seguridad."
  type        = string
}

variable "allowed_signing_algorithms" {
  description = "Algoritmos de firma permitidos, conforme a la DPSC."
  type        = list(string)
  default     = ["RSASSA_PKCS1_V1_5_SHA_256", "RSASSA_PSS_SHA_256"]
}

variable "log_retention_days" {
  description = "Retención de los logs de aplicación en CloudWatch."
  type        = number
  default     = 731
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}

variable "aws_service_prefix_list_ids" {
  description = <<-EOT
    Listas de prefijos gestionadas de los servicios de AWS que el servicio
    alcanza (S3, DynamoDB). Se usan en lugar de rangos fijos porque AWS las
    mantiene al día; un rango escrito a mano queda obsoleto sin aviso.
  EOT
  type        = list(string)
  default     = []
}

variable "external_https_cidr_blocks" {
  description = <<-EOT
    Rangos externos que el servicio puede alcanzar por HTTPS: la autoridad de
    sellado de tiempo y el proveedor de identidad del inquilino. Vacío mientras
    la TSA no esté contratada (B-01), lo que impide que el nivel 2 opere — que es
    lo que el ADR-0007 ya declara.

    Declarar destinos concretos en lugar de abrir el puerto entero es lo que hace
    que una exfiltración desde el contenedor no tenga salida.
  EOT
  type        = list(string)
  default     = []
}
