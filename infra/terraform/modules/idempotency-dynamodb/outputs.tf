output "table_name" {
  description = "Nombre de la tabla, para la configuración del servicio."
  value       = aws_dynamodb_table.idempotency.name
}

output "table_arn" {
  description = "ARN de la tabla, para las políticas de IAM del servicio."
  value       = aws_dynamodb_table.idempotency.arn
}
