variable "jurisdiction_code" {
  description = "Código ISO de la jurisdicción activa."
  type        = string
}

variable "jurisdiction_name" {
  description = "Nombre de la jurisdicción, para el mensaje de error."
  type        = string
}

variable "jurisdiction_minimum_retention_days" {
  description = "Conservación mínima que exige la jurisdicción, exportada desde su perfil."
  type        = number
}

variable "jurisdiction_retention_legal_basis" {
  description = "Norma que fundamenta el plazo, para que el error diga por qué."
  type        = string
}

variable "jurisdiction_legally_validated" {
  description = "Si el perfil pasó revisión de asesoría legal local."
  type        = bool
}

variable "configured_retention_days" {
  description = "Retención de S3 Object Lock configurada en el entorno."
  type        = number
}

variable "environment" {
  description = "Entorno lógico. Solo `dev` admite una jurisdicción sin validar."
  type        = string
}
