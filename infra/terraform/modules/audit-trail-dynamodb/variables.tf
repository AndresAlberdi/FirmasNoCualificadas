variable "table_name" {
  description = "Nombre de la tabla de la pista de auditoría forense."
  type        = string
  default     = "PSCNC_Audit_Trail"
}

variable "dashboard_audit_table_name" {
  description = "Nombre de la tabla de auditoría de accesos del panel B2B."
  type        = string
  default     = "PSCNC_Dashboard_Audit_Log"
}

variable "kms_key_arn" {
  description = "ARN de la clave KMS gestionada por el cliente para cifrado en reposo."
  type        = string
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}
