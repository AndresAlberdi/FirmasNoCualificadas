output "secops_topic_arn" {
  description = "Tópico SNS de alertas de seguridad."
  value       = aws_sns_topic.secops.arn
}

output "trail_name" {
  description = "Nombre del trail de CloudTrail."
  value       = aws_cloudtrail.main.name
}

output "trail_log_group_name" {
  description = "Grupo de logs donde CloudTrail entrega los eventos."
  value       = aws_cloudwatch_log_group.trail.name
}
