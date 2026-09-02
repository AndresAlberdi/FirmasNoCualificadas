variable "environment" {
  description = "Entorno lógico del despliegue."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subredes privadas para el VPC Link."
  type        = list(string)
}

variable "vpc_link_security_group_ids" {
  description = "Security groups del VPC Link."
  type        = list(string)
}

variable "listener_arn" {
  description = "ARN del listener del balanceador interno que expone el servicio de firma."
  type        = string
}

variable "integration_timeout_ms" {
  description = "Tiempo máximo de la integración. La firma con TSA puede tardar; 29 s es el máximo de API Gateway."
  type        = number
  default     = 29000
}

variable "rate_limit_per_five_minutes" {
  description = "Peticiones máximas por IP en una ventana de cinco minutos (regla WAF)."
  type        = number
  default     = 2000
}

variable "throttling_rate_limit" {
  description = "Peticiones por segundo sostenidas por etapa."
  type        = number
  default     = 100
}

variable "throttling_burst_limit" {
  description = "Ráfaga máxima admitida por etapa."
  type        = number
  default     = 200
}

variable "allowed_cors_origins" {
  description = "Orígenes permitidos para el panel B2B."
  type        = list(string)
  default     = []
}

variable "domain_name" {
  description = "Dominio personalizado de la API. Nulo para omitirlo."
  type        = string
  default     = null
}

variable "certificate_arn" {
  description = "ARN del certificado ACM del dominio personalizado."
  type        = string
  default     = null
}

variable "mtls_truststore_uri" {
  description = "URI en S3 del truststore de CAs de clientes B2B para mTLS. Nulo para desactivar."
  type        = string
  default     = null
}

variable "mtls_truststore_version" {
  description = "Versión del objeto del truststore en S3."
  type        = string
  default     = null
}

variable "dashboard_callback_urls" {
  description = "URLs de retorno OAuth del panel B2B."
  type        = list(string)
  default     = []
}

variable "dashboard_logout_urls" {
  description = "URLs de cierre de sesión del panel B2B."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "Retención de los logs de acceso de la API."
  type        = number
  default     = 731
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}

variable "kms_key_arn" {
  description = <<-EOT
    Clave KMS con la que se cifra el grupo de logs de acceso. Ese log registra la
    dirección IP y la cabecera del firmante, que son evidencia pericial: se cifra
    con la misma clave que el resto de la evidencia.
  EOT
  type        = string
}
