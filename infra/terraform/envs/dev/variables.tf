variable "region" {
  description = "Región de AWS del despliegue."
  type        = string
  default     = "us-east-1"
}

variable "aws_profile" {
  description = "Perfil de credenciales local. Nulo en CI (se usa OIDC)."
  type        = string
  default     = null
}

# --------------------------------------------------------------------- Red ---
variable "vpc_id" {
  description = "VPC existente donde se despliega la plataforma."
  type        = string
}

variable "private_subnet_ids" {
  description = "Subredes privadas (mínimo dos zonas de disponibilidad)."
  type        = list(string)
}

variable "vpc_cidr_blocks" {
  description = "Bloques CIDR internos autorizados a alcanzar el balanceador."
  type        = list(string)
}

variable "internal_certificate_arn" {
  description = "Certificado ACM del listener interno HTTPS."
  type        = string
}

# ------------------------------------------------------------------- Cripto --
variable "ca_key_spec" {
  description = "Especificación de la clave de la CA intermedia."
  type        = string
  default     = "RSA_4096"
}

variable "secops_admin_role_arns" {
  description = "Roles de administración de SecOps (incluye el rol de emergencia)."
  type        = list(string)
}

# ------------------------------------------------------------ Persistencia ---
variable "signed_bucket_name" {
  description = "Nombre global del bucket de documentos firmados."
  type        = string
}

variable "evidence_bucket_name" {
  description = "Nombre global del bucket WORM de evidencias."
  type        = string
}

variable "trail_bucket_name" {
  description = "Nombre global del bucket de CloudTrail."
  type        = string
}

variable "crl_bucket_name" {
  description = "Nombre global del bucket de publicación de la CRL."
  type        = string
}

variable "object_lock_retention_days" {
  description = "Retención WORM de las evidencias."
  type        = number
  default     = 1095
}

# ------------------------------------------------------------- Aplicación ----
variable "container_image" {
  description = "Imagen del servicio de firma. En producción debe referenciarse por digest."
  type        = string
}

variable "crl_lambda_package_path" {
  description = "Ruta al ZIP de la función de publicación de CRL (generado por scripts/build-lambda.sh)."
  type        = string
  default     = "../../../../dist/crl_publisher.zip"
}

variable "secret_arns" {
  description = "ARNs de secretos legibles por el servicio."
  type        = list(string)
  default     = []
}

variable "container_secrets" {
  description = "Secretos inyectados como variables de entorno."
  type = list(object({
    name       = string
    value_from = string
  }))
  default = []
}

# --------------------------------------------------------------- Perímetro ---
variable "allowed_cors_origins" {
  description = "Orígenes permitidos para el panel B2B."
  type        = list(string)
  default     = []
}

variable "dashboard_callback_urls" {
  description = "URLs de retorno OAuth del panel."
  type        = list(string)
  default     = []
}

variable "dashboard_logout_urls" {
  description = "URLs de cierre de sesión del panel."
  type        = list(string)
  default     = []
}

# ----------------------------------------------------------- Observabilidad --
variable "secops_email_endpoints" {
  description = "Correos suscritos a las alertas de seguridad."
  type        = list(string)
  default     = []
}

variable "enable_guardduty" {
  description = "Habilita GuardDuty en la cuenta."
  type        = bool
  default     = true
}

# ---------------------------------------------------------- Jurisdicción -----
# Estas variables NO se editan a mano: las genera
# `scripts/exportar-jurisdiccion.py` en `jurisdiccion.auto.tfvars` a partir del
# perfil de `services/src/jurisdictions/` (ADR-0008). Duplicar acá el plazo de
# conservación sería tener dos fuentes de verdad para un dato con consecuencia
# legal: si divergieran, la infraestructura conservaría la evidencia menos tiempo
# del que la constancia le promete al firmante.

variable "jurisdiction_code" {
  description = "Código ISO de la jurisdicción activa. Generado desde el perfil."
  type        = string

  validation {
    condition     = can(regex("^[A-Z]{2}$", var.jurisdiction_code))
    error_message = "El código de jurisdicción debe ser ISO 3166-1 alfa-2 en mayúsculas."
  }
}

variable "jurisdiction_name" {
  description = "Nombre de la jurisdicción, para etiquetas y mensajes de error."
  type        = string
}

variable "jurisdiction_minimum_retention_days" {
  description = "Conservación mínima de evidencia que exige la jurisdicción."
  type        = number
}

variable "jurisdiction_retention_legal_basis" {
  description = "Norma que fundamenta el plazo de conservación."
  type        = string
}

variable "jurisdiction_incident_notification_hours" {
  description = "Plazo máximo para notificar un incidente al regulador."
  type        = number
}

variable "jurisdiction_legally_validated" {
  description = "Si el perfil pasó revisión de asesoría legal local."
  type        = bool
}

# ------------------------------------------------------------- Inquilinos ----
variable "tenants" {
  description = <<-EOT
    Inquilinos con claves propias de sello de acta y de cifrado de evidencias
    (ADR-0006). Dar de alta un inquilino es una operación de infraestructura, no
    un registro en una tabla: crea claves, alias y políticas.
  EOT
  type = map(object({
    acta_seal_key_version = optional(number, 1)
    evidence_key_version  = optional(number, 1)
  }))
  default = {}
}

variable "break_glass_role_arns" {
  description = "Roles autorizados a programar la eliminación de una clave (procedimiento de emergencia)."
  type        = list(string)
  default     = []
}
