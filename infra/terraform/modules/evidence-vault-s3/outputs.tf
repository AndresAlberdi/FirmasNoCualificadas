output "signed_bucket_name" {
  description = "Nombre del bucket de documentos firmados."
  value       = aws_s3_bucket.signed_vault.id
}

output "signed_bucket_arn" {
  description = "ARN del bucket de documentos firmados."
  value       = aws_s3_bucket.signed_vault.arn
}

output "evidence_bucket_name" {
  description = "Nombre del bucket WORM de evidencias."
  value       = aws_s3_bucket.evidence_trail.id
}

output "evidence_bucket_arn" {
  description = "ARN del bucket WORM de evidencias."
  value       = aws_s3_bucket.evidence_trail.arn
}
