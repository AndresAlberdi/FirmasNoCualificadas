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
  description = "Entorno lógico del despliegue (dev, staging, prod)."
  type        = string
}

variable "key_alias" {
  description = <<-DESC
    Alias de la clave KMS, sin el prefijo 'alias/'. Sin valor por defecto a
    propósito: el alias identifica a la CA de quien despliega, y heredar el
    nombre de otro produciría una CA que dice ser de alguien que no es.
  DESC
  type        = string
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
