output "key_arn" {
  description = "ARN de la clave KMS de la CA intermedia."
  value       = aws_kms_key.intermediate_ca.arn
}

output "key_id" {
  description = "Identificador de la clave KMS de la CA intermedia."
  value       = aws_kms_key.intermediate_ca.key_id
}

output "key_alias" {
  description = "Alias completo de la clave."
  value       = aws_kms_alias.intermediate_ca.name
}
