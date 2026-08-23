output "cluster_name" {
  description = "Nombre del clúster ECS."
  value       = aws_ecs_cluster.this.name
}

output "service_name" {
  description = "Nombre del servicio ECS de firma."
  value       = aws_ecs_service.signer.name
}

output "task_role_arn" {
  description = "ARN del rol de la tarea (principal autorizado a kms:Sign)."
  value       = aws_iam_role.task.arn
}

output "security_group_id" {
  description = "Security group del servicio."
  value       = aws_security_group.service.id
}

output "log_group_name" {
  description = "Grupo de logs del servicio."
  value       = aws_cloudwatch_log_group.service.name
}
