variable "environment" {
  description = "Entorno lógico del despliegue."
  type        = string
}

variable "account_id" {
  description = "Identificador de la cuenta de AWS."
  type        = string
}

variable "kms_key_arn" {
  description = "ARN de la clave KMS para cifrar logs y notificaciones."
  type        = string
}

variable "trail_bucket_name" {
  description = "Bucket destino de CloudTrail."
  type        = string
}

variable "trail_retention_days" {
  description = "Retención de los archivos de CloudTrail en S3."
  type        = number
  default     = 1095
}

variable "log_retention_days" {
  description = "Retención de los grupos de logs en CloudWatch."
  type        = number
  default     = 731
}

variable "data_event_bucket_arns" {
  description = "Prefijos de ARN de los buckets cuyos eventos de datos se registran."
  type        = list(string)
}

variable "secops_email_endpoints" {
  description = "Correos del equipo de SecOps suscritos a las alertas."
  type        = list(string)
  default     = []
}

variable "kms_sign_alarm_threshold" {
  description = "Umbral de firmas en cinco minutos que dispara la alarma de anomalía."
  type        = number
  default     = 500
}

variable "expected_signer_role_name" {
  description = "Nombre del rol legítimo del servicio de firma; cualquier otro principal que invoque kms:Sign dispara SEV-1."
  type        = string
}

variable "enable_guardduty" {
  description = "Habilita GuardDuty. Desactívelo si ya existe un detector en la cuenta."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}

variable "kms_context_mismatch_threshold" {
  description = <<-EOT
    Descifrados rechazados por contexto en cinco minutos que disparan la alarma.
    No es cero porque un reintento tras una rotación puede producir uno aislado;
    una racha, en cambio, indica un error de enrutamiento entre inquilinos o un
    intento de acceso cruzado.
  EOT
  type        = number
  default     = 3
}
