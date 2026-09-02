variable "table_name" {
  description = "Nombre de la tabla de idempotencia."
  type        = string
}

variable "kms_key_arn" {
  description = "Clave KMS con la que se cifra la tabla."
  type        = string
}

variable "tags" {
  description = "Etiquetas comunes del despliegue."
  type        = map(string)
  default     = {}
}
