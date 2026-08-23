variable "signed_bucket_name" {
  description = "Nombre global del bucket de documentos firmados."
  type        = string
}

variable "evidence_bucket_name" {
  description = "Nombre global del bucket WORM de expedientes de evidencia."
  type        = string
}

variable "kms_key_arn" {
  description = "ARN de la clave KMS para cifrado en reposo (SSE-KMS)."
  type        = string
}

variable "object_lock_retention_days" {
  description = "Retención por defecto en modo COMPLIANCE. Mínimo legal: 2 años desde el fin de los efectos jurídicos del documento."
  type        = number
  default     = 1095 # 3 años: 2 de exigencia legal + 1 de margen procesal

  validation {
    condition     = var.object_lock_retention_days >= 730
    error_message = "La retención no puede ser inferior a 730 días (2 años) por exigencia regulatoria."
  }
}

variable "object_lock_admin_role_arns" {
  description = "Roles excluidos de la denegación explícita de cambios de Object Lock (solo administración de emergencia; en modo COMPLIANCE tampoco pueden borrar)."
  type        = list(string)
  default     = []
}

variable "signed_noncurrent_expiration_days" {
  description = "Días tras los cuales expiran las versiones no vigentes del bucket de firmados."
  type        = number
  default     = 1095
}

variable "access_log_bucket" {
  description = "Bucket destino de los logs de acceso a S3. Nulo para desactivar."
  type        = string
  default     = null
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}
