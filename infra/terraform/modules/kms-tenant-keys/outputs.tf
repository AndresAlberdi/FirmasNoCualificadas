output "acta_seal_key_arn" {
  description = "ARN de la clave de sello del acta. Para políticas de IAM, no para el código."
  value       = aws_kms_key.acta_seal.arn
}

output "acta_seal_key_alias" {
  description = <<-EOT
    Alias versionado de la clave de sello. **Es lo que consume el servicio**: el
    código selecciona la clave por alias y nunca por identificador, para que una
    rotación sea un cambio de configuración y no un despliegue. Viaja además como
    `kid` en el sobre JWS del acta, de modo que un verificador sepa con qué clave
    pública comprobar el sello.
  EOT
  value       = aws_kms_alias.acta_seal.name
}

output "evidence_key_arn" {
  description = "ARN de la clave de cifrado de evidencias. Para SSE-KMS de los buckets y la tabla."
  value       = aws_kms_key.evidence.arn
}

output "evidence_key_alias" {
  description = "Alias versionado de la clave de cifrado de evidencias."
  value       = aws_kms_alias.evidence.name
}

output "tenant_id" {
  description = "Inquilino al que pertenecen estas claves; debe coincidir con el contexto de cifrado."
  value       = var.tenant_id
}
