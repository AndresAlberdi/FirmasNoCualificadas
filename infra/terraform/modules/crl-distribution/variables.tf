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
  description = "Entorno lógico del despliegue."
  type        = string
}

variable "crl_bucket_name" {
  description = "Bucket privado que almacena la CRL publicada."
  type        = string
}

variable "crl_object_key" {
  description = "Ruta del objeto de la CRL dentro del bucket."
  type        = string
  default     = "pscnc/intermediate.crl"
}

variable "crl_domain_name" {
  description = "Dominio del punto de distribución de la CRL. Debe coincidir con el crlDistributionPoints de los certificados emitidos."
  type        = string
  default     = null
}

variable "crl_certificate_arn" {
  description = "Certificado ACM en us-east-1 para el dominio de la CRL."
  type        = string
  default     = null
}

variable "crl_cache_ttl_seconds" {
  description = "TTL de caché en CloudFront. Corto para permitir propagación rápida de una revocación de emergencia."
  type        = number
  default     = 300
}

variable "crl_validity_hours" {
  description = "Horas de validez declaradas en el campo nextUpdate de la CRL."
  type        = number
  default     = 72
}

variable "schedule_expression" {
  description = "Expresión de EventBridge para la regeneración periódica."
  type        = string
  default     = "rate(24 hours)"
}

variable "kms_ca_key_arn" {
  description = "ARN de la clave KMS de la CA intermedia que firma la CRL."
  type        = string
}

variable "kms_evidence_key_arn" {
  description = "ARN de la clave KMS simétrica con la que se cifra el bucket de la CRL."
  type        = string
}

variable "lambda_package_path" {
  description = "Ruta local al paquete ZIP de la función de publicación de la CRL."
  type        = string
}

variable "secops_topic_arn" {
  description = "Tópico SNS de alertas de seguridad."
  type        = string
}

variable "tags" {
  description = "Etiquetas comunes del proyecto."
  type        = map(string)
  default     = {}
}
