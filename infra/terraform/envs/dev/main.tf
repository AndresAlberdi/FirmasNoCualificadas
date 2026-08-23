###############################################################################
# Entorno: dev
#
# Composición completa de la plataforma FENC-PY. La red (VPC, subredes) se
# asume preexistente y se referencia por identificador: la creación de la red
# corporativa no es competencia de este stack.
#
# Orden de dependencia real:
#   observability → kms → (dynamodb, s3) → alb → signer-service → api-edge
#                                            └→ crl-distribution
###############################################################################

terraform {
  required_version = ">= 1.9.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.70"
    }
  }
}

provider "aws" {
  region  = var.region
  profile = var.aws_profile

  default_tags {
    tags = local.common_tags
  }
}

data "aws_caller_identity" "current" {}

locals {
  environment = "dev"

  common_tags = {
    Project     = "FENC-PY"
    Environment = local.environment
    Owner       = "PSCNC-SecOps"
    ManagedBy   = "terraform"
    Regulation  = "Ley-6822-2021"
  }

  account_id = data.aws_caller_identity.current.account_id

  # El nombre del rol de la tarea es determinista (lo compone el módulo
  # signer-service). Se referencia por ARN construido y no por el output del
  # módulo para romper el ciclo kms ↔ signer-service: el servicio necesita el
  # ARN de la clave y la política de la clave necesita el ARN del rol.
  signer_task_role_name = "pscnc-signer-${local.environment}-task-role"
  signer_task_role_arn  = "arn:aws:iam::${local.account_id}:role/${local.signer_task_role_name}"
}

# ------------------------------------------------------------ Observabilidad
module "observability" {
  source = "../../modules/observability"

  environment               = local.environment
  account_id                = local.account_id
  kms_key_arn               = aws_kms_key.data.arn
  trail_bucket_name         = var.trail_bucket_name
  data_event_bucket_arns    = [module.evidence_vault.evidence_bucket_arn, module.evidence_vault.signed_bucket_arn]
  secops_email_endpoints    = var.secops_email_endpoints
  expected_signer_role_name = local.signer_task_role_name
  enable_guardduty          = var.enable_guardduty
  tags                      = local.common_tags
}

# ------------------------------------- Clave de datos (distinta de la CA) ----
resource "aws_kms_key" "data" {
  description             = "PSCNC ${local.environment} - cifrado de datos en reposo"
  enable_key_rotation     = true
  deletion_window_in_days = 30
  tags                    = local.common_tags
}

resource "aws_kms_alias" "data" {
  name          = "alias/pscnc-data-${local.environment}"
  target_key_id = aws_kms_key.data.key_id
}

# ---------------------------------------------------------- CA intermedia ----
module "intermediate_ca" {
  source = "../../modules/kms-intermediate-ca"

  environment      = local.environment
  key_alias        = "pscnc-paraguay-intermediate-ca-${local.environment}"
  key_spec         = var.ca_key_spec
  admin_role_arns  = var.secops_admin_role_arns
  signer_role_arns = [local.signer_task_role_arn]
  tags             = local.common_tags
}

# ------------------------------------------------------------ Persistencia ---
module "audit_trail" {
  source = "../../modules/audit-trail-dynamodb"

  table_name  = "PSCNC_Audit_Trail_${local.environment}"
  kms_key_arn = aws_kms_key.data.arn
  tags        = local.common_tags
}

module "evidence_vault" {
  source = "../../modules/evidence-vault-s3"

  signed_bucket_name          = var.signed_bucket_name
  evidence_bucket_name        = var.evidence_bucket_name
  kms_key_arn                 = aws_kms_key.data.arn
  object_lock_retention_days  = var.object_lock_retention_days
  object_lock_admin_role_arns = var.secops_admin_role_arns
  tags                        = local.common_tags
}

# ------------------------------------------------- Balanceador interno -------
resource "aws_security_group" "alb" {
  name        = "pscnc-alb-${local.environment}"
  description = "Balanceador interno del servicio de firma"
  vpc_id      = var.vpc_id

  ingress {
    description = "Entrada desde el VPC Link de API Gateway"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.vpc_cidr_blocks
  }

  egress {
    description = "Salida hacia las tareas del servicio"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = var.vpc_cidr_blocks
  }

  tags = local.common_tags
}

resource "aws_lb" "internal" {
  name                       = "pscnc-signer-${local.environment}"
  internal                   = true
  load_balancer_type         = "application"
  security_groups            = [aws_security_group.alb.id]
  subnets                    = var.private_subnet_ids
  drop_invalid_header_fields = true
  enable_deletion_protection = false # dev
  tags                       = local.common_tags
}

resource "aws_lb_target_group" "signer" {
  name        = "pscnc-signer-${local.environment}"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = var.vpc_id

  health_check {
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  deregistration_delay = 30
  tags                 = local.common_tags
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.internal.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.internal_certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.signer.arn
  }
}

# ------------------------------------------------------- Servicio de firma ---
module "signer_service" {
  source = "../../modules/signer-service"

  environment                     = local.environment
  region                          = var.region
  account_id                      = local.account_id
  vpc_id                          = var.vpc_id
  private_subnet_ids              = var.private_subnet_ids
  load_balancer_security_group_id = aws_security_group.alb.id
  target_group_arn                = aws_lb_target_group.signer.arn
  container_image                 = var.container_image
  desired_count                   = 1
  max_capacity                    = 3

  kms_ca_key_arn       = module.intermediate_ca.key_arn
  kms_data_key_arn     = aws_kms_key.data.arn
  audit_table_arn      = module.audit_trail.table_arn
  audit_table_name     = module.audit_trail.table_name
  signed_bucket_arn    = module.evidence_vault.signed_bucket_arn
  signed_bucket_name   = module.evidence_vault.signed_bucket_name
  evidence_bucket_arn  = module.evidence_vault.evidence_bucket_arn
  evidence_bucket_name = module.evidence_vault.evidence_bucket_name
  secret_arns          = var.secret_arns
  container_secrets    = var.container_secrets
  secops_topic_arn     = module.observability.secops_topic_arn
  tags                 = local.common_tags
}

# ------------------------------------------------------------ Perímetro ------
module "api_edge" {
  source = "../../modules/api-edge"

  environment                 = local.environment
  private_subnet_ids          = var.private_subnet_ids
  vpc_link_security_group_ids = [aws_security_group.alb.id]
  listener_arn                = aws_lb_listener.https.arn
  allowed_cors_origins        = var.allowed_cors_origins
  dashboard_callback_urls     = var.dashboard_callback_urls
  dashboard_logout_urls       = var.dashboard_logout_urls
  tags                        = local.common_tags
}

# ------------------------------------------------------ Distribución de CRL --
module "crl_distribution" {
  source = "../../modules/crl-distribution"

  environment         = local.environment
  crl_bucket_name     = var.crl_bucket_name
  kms_ca_key_arn      = module.intermediate_ca.key_arn
  lambda_package_path = var.crl_lambda_package_path
  secops_topic_arn    = module.observability.secops_topic_arn
  tags                = local.common_tags
}
