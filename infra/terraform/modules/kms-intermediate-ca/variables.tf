variable "environment" {
  description = "Entorno lógico del despliegue (dev, staging, prod)."
  type        = string
}

variable "key_alias" {
  description = "Alias de la clave KMS, sin el prefijo 'alias/'."
  type        = string
  default     = "pscnc-paraguay-intermediate-ca"
}

variable "key_spec" {
  description = "Especificación de la clave asimétrica. RSA_4096 es el estándar para CA subordinadas; RSA_2048 reduce latencia en firmas masivas."
  type        = string
  default     = "RSA_4096"

  validation {
    condition     = contains(["RSA_2048", "RSA_4096", "ECC_NIST_P256"], var.key_spec)
    error_message = "key_spec debe ser RSA_2048, RSA_4096 o ECC_NIST_P256."
  }
}

variable "allowed_signing_algorithms" {
  description = "Algoritmos de firma habilitados para el servicio, conforme a la DPSC."
  type        = list(string)
  default     = ["RSASSA_PKCS1_V1_5_SHA_256", "RSASSA_PSS_SHA_256"]
}

variable "admin_role_arns" {
  description = "Roles de SecOps con permisos de administración de la clave (sin permiso de firma)."
  type        = list(string)

  validation {
    condition     = length(var.admin_role_arns) > 0
    error_message = "Debe declararse al menos un rol administrador para no dejar la clave sin gobierno."
  }
}

variable "signer_role_arns" {
  description = "Roles del servicio de firma autorizados a invocar kms:Sign (sin permisos de administración)."
  type        = list(string)
}

variable "deletion_window_in_days" {
  description = "Ventana de espera antes de la eliminación efectiva de la clave. Se usa el máximo por tratarse de un activo crítico."
  type        = number
  default     = 30

  validation {
    condition     = var.deletion_window_in_days >= 30
    error_message = "Para la clave de la CA intermedia la ventana mínima aceptada es de 30 días."
  }
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}
