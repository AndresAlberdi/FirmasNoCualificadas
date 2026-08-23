###############################################################################
# Módulo: api-edge
#
# Perímetro de la API B2B: WAF con reglas OWASP y límite de tasa, API Gateway
# HTTP API con integración privada al balanceador interno, y pool de Cognito
# para el panel B2B (MFA obligatorio).
#
# NOTA sobre mTLS: HTTP API soporta mTLS únicamente sobre dominio personalizado
# con un truststore en S3. Se habilita cuando var.mtls_truststore_uri no es nulo.
###############################################################################

locals {
  name = "pscnc-api-${var.environment}"
}

# ------------------------------------------------------------------ WAF -----
resource "aws_wafv2_web_acl" "api" {
  name        = "${local.name}-waf"
  description = "Proteccion perimetral de la API B2B PSCNC"
  scope       = "REGIONAL"

  default_action {
    allow {}
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 1
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesCommonRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "common-rules"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 2
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "known-bad-inputs"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesAmazonIpReputationList"
    priority = 3
    override_action {
      none {}
    }
    statement {
      managed_rule_group_statement {
        vendor_name = "AWS"
        name        = "AWSManagedRulesAmazonIpReputationList"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "ip-reputation"
      sampled_requests_enabled   = true
    }
  }

  # Límite de tasa por dirección IP de origen.
  rule {
    name     = "RateLimitPerSourceIp"
    priority = 10
    action {
      block {}
    }
    statement {
      rate_based_statement {
        limit              = var.rate_limit_per_five_minutes
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "rate-limit-ip"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "${local.name}-waf"
    sampled_requests_enabled   = true
  }

  tags = var.tags
}

# ------------------------------------------------------------ API Gateway ---
resource "aws_apigatewayv2_api" "b2b" {
  name          = local.name
  protocol_type = "HTTP"
  description   = "API B2B de firma electronica no cualificada"

  cors_configuration {
    allow_origins = var.allowed_cors_origins
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "x-pscnc-timestamp", "x-pscnc-signature"]
    max_age       = 300
  }

  tags = var.tags
}

resource "aws_apigatewayv2_vpc_link" "private" {
  name               = "${local.name}-vpclink"
  security_group_ids = var.vpc_link_security_group_ids
  subnet_ids         = var.private_subnet_ids
  tags               = var.tags
}

resource "aws_apigatewayv2_integration" "signer" {
  api_id                 = aws_apigatewayv2_api.b2b.id
  integration_type       = "HTTP_PROXY"
  integration_method     = "ANY"
  integration_uri        = var.listener_arn
  connection_type        = "VPC_LINK"
  connection_id          = aws_apigatewayv2_vpc_link.private.id
  payload_format_version = "1.0"
  timeout_milliseconds   = var.integration_timeout_ms
}

resource "aws_apigatewayv2_route" "proxy" {
  api_id    = aws_apigatewayv2_api.b2b.id
  route_key = "ANY /v1/{proxy+}"
  target    = "integrations/${aws_apigatewayv2_integration.signer.id}"
}

resource "aws_cloudwatch_log_group" "access" {
  name              = "/aws/apigateway/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.b2b.id
  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.access.arn
    # La cabecera Authorization jamás se registra.
    format = jsonencode({
      requestId      = "$context.requestId"
      ip             = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      protocol       = "$context.protocol"
      responseLength = "$context.responseLength"
      integrationErr = "$context.integrationErrorMessage"
      userAgent      = "$context.identity.userAgent"
      tlsVersion     = "$context.identity.clientCert.serialNumber"
    })
  }

  default_route_settings {
    throttling_burst_limit   = var.throttling_burst_limit
    throttling_rate_limit    = var.throttling_rate_limit
    detailed_metrics_enabled = true
  }

  tags = var.tags
}

resource "aws_wafv2_web_acl_association" "api" {
  resource_arn = aws_apigatewayv2_stage.default.arn
  web_acl_arn  = aws_wafv2_web_acl.api.arn
}

# ------------------------------------- Dominio personalizado con mTLS opcional
resource "aws_apigatewayv2_domain_name" "custom" {
  count       = var.domain_name == null ? 0 : 1
  domain_name = var.domain_name

  domain_name_configuration {
    certificate_arn = var.certificate_arn
    endpoint_type   = "REGIONAL"
    security_policy = "TLS_1_2" # valor máximo admitido por la API; TLS 1.3 se negocia si el cliente lo soporta
  }

  dynamic "mutual_tls_authentication" {
    for_each = var.mtls_truststore_uri == null ? [] : [1]
    content {
      truststore_uri     = var.mtls_truststore_uri
      truststore_version = var.mtls_truststore_version
    }
  }

  tags = var.tags
}

resource "aws_apigatewayv2_api_mapping" "custom" {
  count       = var.domain_name == null ? 0 : 1
  api_id      = aws_apigatewayv2_api.b2b.id
  domain_name = aws_apigatewayv2_domain_name.custom[0].id
  stage       = aws_apigatewayv2_stage.default.id
}

# ---------------------------------------------- Cognito para el panel B2B ----
resource "aws_cognito_user_pool" "dashboard" {
  name                     = "${local.name}-dashboard"
  mfa_configuration        = "ON"
  auto_verified_attributes = ["email"]
  deletion_protection      = "ACTIVE"

  software_token_mfa_configuration {
    enabled = true
  }

  password_policy {
    minimum_length                   = 14
    require_lowercase                = true
    require_uppercase                = true
    require_numbers                  = true
    require_symbols                  = true
    temporary_password_validity_days = 3
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  user_pool_add_ons {
    advanced_security_mode = "ENFORCED"
  }

  tags = var.tags
}

# Roles del panel según la matriz RBAC de la especificación del dashboard.
resource "aws_cognito_user_group" "roles" {
  for_each = toset([
    "B2B_Super_Admin",
    "B2B_Legal_Auditor",
    "B2B_Operator",
    "B2B_Developer",
  ])

  name         = each.value
  user_pool_id = aws_cognito_user_pool.dashboard.id
  description  = "Rol RBAC del panel B2B: ${each.value}"
}

resource "aws_cognito_user_pool_client" "dashboard" {
  name                                 = "${local.name}-dashboard-spa"
  user_pool_id                         = aws_cognito_user_pool.dashboard.id
  generate_secret                      = false
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes                 = ["openid", "email", "profile"]
  supported_identity_providers         = ["COGNITO"]
  callback_urls                        = var.dashboard_callback_urls
  logout_urls                          = var.dashboard_logout_urls

  access_token_validity  = 15
  id_token_validity      = 15
  refresh_token_validity = 8
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "hours"
  }

  explicit_auth_flows = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  enable_token_revocation = true
  prevent_user_existence_errors = "ENABLED"
}
