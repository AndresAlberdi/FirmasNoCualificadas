output "api_endpoint" {
  description = "Endpoint de la API B2B."
  value       = module.api_edge.api_endpoint
}

output "intermediate_ca_key_arn" {
  description = "ARN de la clave de la CA intermedia (declarar en la DPSC)."
  value       = module.intermediate_ca.key_arn
}

output "audit_table_name" {
  description = "Tabla de la pista de auditoría."
  value       = module.audit_trail.table_name
}

output "evidence_bucket_name" {
  description = "Bucket WORM de evidencias."
  value       = module.evidence_vault.evidence_bucket_name
}

output "signed_bucket_name" {
  description = "Bucket de documentos firmados."
  value       = module.evidence_vault.signed_bucket_name
}

output "crl_public_url" {
  description = "URL de la CRL a declarar en el perfil de certificados (crlDistributionPoints)."
  value       = module.crl_distribution.crl_public_url
}

output "dashboard_user_pool_id" {
  description = "Pool de Cognito del panel B2B."
  value       = module.api_edge.user_pool_id
}

output "secops_topic_arn" {
  description = "Tópico SNS de alertas de seguridad."
  value       = module.observability.secops_topic_arn
}
