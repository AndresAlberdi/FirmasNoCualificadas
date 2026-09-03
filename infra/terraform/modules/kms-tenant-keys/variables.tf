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

variable "tenant_id" {
  description = "Identificador del inquilino. Forma parte del alias y del contexto de cifrado."
  type        = string

  validation {
    # El mismo formato que acepta `b2b_client_id` en la pista de auditoría: si
    # divergieran, el contexto de cifrado no coincidiría con el dato persistido.
    condition     = can(regex("^[a-zA-Z0-9_.-]{2,40}$", var.tenant_id))
    error_message = "El identificador del inquilino admite letras, dígitos, punto, guion y guion bajo (2 a 40 caracteres)."
  }
}

variable "environment" {
  description = "Entorno lógico del despliegue (dev, staging, prod)."
  type        = string

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "El entorno debe ser dev, staging o prod."
  }
}

variable "region" {
  description = "Región de AWS. Acota el permiso `kms:ViaService` de S3 y DynamoDB."
  type        = string
}

variable "signer_role_arns" {
  description = "Roles del servicio de firma que pueden usar las claves. Nunca roles humanos."
  type        = list(string)

  validation {
    condition     = length(var.signer_role_arns) > 0
    error_message = "Debe declararse al menos un rol de servicio; una clave sin usuario no cumple ninguna función."
  }
}

variable "admin_role_arns" {
  description = "Roles de administración. No pueden firmar ni descifrar (separación de funciones)."
  type        = list(string)
  default     = []
}

variable "break_glass_role_arns" {
  description = <<-EOT
    Roles autorizados a programar la eliminación de una clave, mediante el
    procedimiento de emergencia. Debe ser un conjunto mínimo y distinto de los
    roles de administración corrientes: eliminar la clave de sello destruye la
    verificabilidad de todas las actas que firmó, y eliminar la de evidencias
    hace ilegible la evidencia que la ley obliga a conservar.
  EOT
  type        = list(string)
  default     = []
}

variable "acta_seal_key_version" {
  description = <<-EOT
    Versión del alias de la clave de sello. Se incrementa al rotar, siguiendo el
    procedimiento manual del runbook: las claves asimétricas de KMS no admiten
    rotación automática. Durante el solapamiento conviven dos versiones, la
    anterior verificando y la nueva firmando.
  EOT
  type        = number
  default     = 1

  validation {
    condition     = var.acta_seal_key_version >= 1
    error_message = "La versión del alias empieza en 1."
  }
}

variable "evidence_key_version" {
  description = "Versión del alias de la clave de evidencias."
  type        = number
  default     = 1

  validation {
    condition     = var.evidence_key_version >= 1
    error_message = "La versión del alias empieza en 1."
  }
}

variable "deletion_window_in_days" {
  description = <<-EOT
    Ventana de espera antes de que una eliminación programada se ejecute. Se fija
    en el máximo que admite KMS: es el último margen para revertir un borrado que
    destruiría evidencia con obligación legal de conservación.
  EOT
  type        = number
  default     = 30

  validation {
    condition     = var.deletion_window_in_days >= 30
    error_message = "La ventana de eliminación no puede ser menor a 30 días para claves con valor probatorio."
  }
}

variable "tags" {
  description = "Etiquetas comunes del despliegue."
  type        = map(string)
  default     = {}
}
