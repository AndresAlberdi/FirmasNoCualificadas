output "table_name" {
  description = "Nombre de la tabla de auditoría."
  value       = aws_dynamodb_table.audit_trail.name
}

output "table_arn" {
  description = "ARN de la tabla de auditoría."
  value       = aws_dynamodb_table.audit_trail.arn
}

output "stream_arn" {
  description = "ARN del stream que alimenta la replicación WORM."
  value       = aws_dynamodb_table.audit_trail.stream_arn
}

output "dashboard_audit_table_name" {
  description = "Nombre de la tabla de auditoría de accesos del panel."
  value       = aws_dynamodb_table.dashboard_audit_log.name
}

output "dashboard_audit_table_arn" {
  description = "ARN de la tabla de auditoría de accesos del panel."
  value       = aws_dynamodb_table.dashboard_audit_log.arn
}
