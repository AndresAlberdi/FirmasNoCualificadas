output "api_endpoint" {
  description = "Endpoint por defecto de la API B2B."
  value       = aws_apigatewayv2_api.b2b.api_endpoint
}

output "api_id" {
  description = "Identificador de la API."
  value       = aws_apigatewayv2_api.b2b.id
}

output "web_acl_arn" {
  description = "ARN del Web ACL de WAF asociado."
  value       = aws_wafv2_web_acl.api.arn
}

output "user_pool_id" {
  description = "Identificador del pool de Cognito del panel B2B."
  value       = aws_cognito_user_pool.dashboard.id
}

output "user_pool_client_id" {
  description = "Cliente SPA del pool de Cognito."
  value       = aws_cognito_user_pool_client.dashboard.id
}
