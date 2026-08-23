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
