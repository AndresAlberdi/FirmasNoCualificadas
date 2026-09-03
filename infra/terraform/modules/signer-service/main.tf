###############################################################################
# Módulo: signer-service
#
# Servicio de firma sobre ECS Fargate en subredes privadas, sin IP pública,
# detrás de un balanceador interno. El acceso a AWS se realiza por VPC
# Endpoints para que el tráfico hacia KMS, S3 y DynamoDB no atraviese Internet.
###############################################################################

locals {
  name = "${var.resource_prefix}-signer-${var.environment}"
}

# ------------------------------------------------------------------- IAM ----
data "aws_iam_policy_document" "task_assume_role" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]

    # Impide que un rol de otra cuenta o servicio asuma esta identidad.
    condition {
      test     = "ArnLike"
      variable = "aws:SourceArn"
      values   = ["arn:aws:ecs:${var.region}:${var.account_id}:*"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [var.account_id]
    }
  }
}

# Rol de la aplicación (permisos de negocio).
resource "aws_iam_role" "task" {
  name               = "${local.name}-task-role"
  assume_role_policy = data.aws_iam_policy_document.task_assume_role.json
  tags               = var.tags
}

# Rol de ejecución (extracción de imagen y logs). Separado por diseño.
resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution-role"
  assume_role_policy = data.aws_iam_policy_document.task_assume_role.json
  tags               = var.tags
}

resource "aws_iam_role_policy_attachment" "execution_managed" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

data "aws_iam_policy_document" "task_permissions" {
  statement {
    sid       = "AllowKmsSigningOnIntermediateCaOnly"
    effect    = "Allow"
    actions   = ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = [var.kms_ca_key_arn]
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = var.allowed_signing_algorithms
    }
  }

  statement {
    sid     = "AllowDataKeyUsageForStorageEncryption"
    effect  = "Allow"
    actions = ["kms:GenerateDataKey", "kms:Decrypt", "kms:Encrypt"]
    # Clave de datos distinta de la clave de la CA: separación de propósitos.
    resources = [var.kms_data_key_arn]
  }

  statement {
    sid       = "AllowWriteSignedDocuments"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:PutObjectTagging", "s3:GetObject"]
    resources = ["${var.signed_bucket_arn}/*"]
  }

  # Sin s3:DeleteObject en la bóveda de evidencias: el servicio escribe y nunca borra.
  statement {
    sid       = "AllowWriteEvidenceOnly"
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:PutObjectTagging", "s3:GetObject"]
    resources = ["${var.evidence_bucket_arn}/*"]
  }

  statement {
    sid       = "AllowAuditTrailWrites"
    effect    = "Allow"
    actions   = ["dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:GetItem", "dynamodb:Query"]
    resources = [var.audit_table_arn, "${var.audit_table_arn}/index/*"]
  }

  statement {
    sid       = "AllowReadB2BSecrets"
    effect    = "Allow"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = var.secret_arns
  }

  statement {
    sid       = "AllowIncidentNotifications"
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [var.secops_topic_arn]
  }
}

resource "aws_iam_role_policy" "task" {
  name   = "${local.name}-task-policy"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task_permissions.json
}

# ------------------------------------------------------------------ Red -----
resource "aws_security_group" "service" {
  name        = "${local.name}-sg"
  description = "Trafico del servicio de firma PSCNC"
  vpc_id      = var.vpc_id

  ingress {
    description     = "Solo desde el balanceador interno"
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [var.load_balancer_security_group_id]
  }

  # El egreso se declara por destino y no como «todo el puerto 443». Un servicio
  # que firma documentos con valor jurídico solo necesita alcanzar tres cosas: los
  # servicios de AWS que usa, la autoridad de sellado de tiempo y el proveedor de
  # identidad del inquilino. Todo lo demás que pudiera salir por 443 —una
  # exfiltración desde el contenedor, por ejemplo— no tiene por qué poder hacerlo.
  #
  # Los servicios de AWS se alcanzan por sus listas de prefijos gestionadas, que
  # AWS mantiene al día: fijar sus rangos a mano quedaría desactualizado.
  egress {
    description     = "Servicios de AWS por sus listas de prefijos gestionadas"
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    prefix_list_ids = var.aws_service_prefix_list_ids
  }

  dynamic "egress" {
    # La autoridad de sellado y el proveedor de identidad se declaran por su
    # rango. Mientras la TSA no esté contratada (B-01 de docs/PENDIENTES.md), la
    # lista está vacía y el nivel 2 no puede operar — que es exactamente lo que
    # el ADR-0007 declara.
    for_each = length(var.external_https_cidr_blocks) > 0 ? [1] : []

    content {
      description = "Autoridad de sellado de tiempo y proveedor de identidad"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = var.external_https_cidr_blocks
    }
  }

  tags = var.tags
}

# ------------------------------------------------------------- Observabilidad
resource "aws_cloudwatch_log_group" "service" {
  name              = "/aws/ecs/${local.name}"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_data_key_arn
  tags              = var.tags
}

# ------------------------------------------------------------------ ECS -----
resource "aws_ecs_cluster" "this" {
  name = "${var.resource_prefix}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.tags
}

resource "aws_ecs_task_definition" "signer" {
  family                   = local.name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([
    {
      name                   = "signer"
      image                  = var.container_image
      essential              = true
      readonlyRootFilesystem = true
      portMappings = [{
        containerPort = var.container_port
        protocol      = "tcp"
      }]
      environment = [
        { name = "PSCNC_ENVIRONMENT", value = var.environment },
        { name = "PSCNC_CRYPTO_BACKEND", value = "kms" },
        { name = "AWS_REGION", value = var.region },
        { name = "PSCNC_KMS_CA_KEY_ID", value = var.kms_ca_key_arn },
        { name = "PSCNC_AUDIT_TABLE", value = var.audit_table_name },
        { name = "PSCNC_SIGNED_BUCKET", value = var.signed_bucket_name },
        { name = "PSCNC_EVIDENCE_BUCKET", value = var.evidence_bucket_name },
      ]
      secrets = [
        for s in var.container_secrets : { name = s.name, valueFrom = s.value_from }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.service.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "signer"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "python -c \"import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:${var.container_port}/health').status==200 else 1)\""]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 20
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_service" "signer" {
  name                              = local.name
  cluster                           = aws_ecs_cluster.this.id
  task_definition                   = aws_ecs_task_definition.signer.arn
  desired_count                     = var.desired_count
  launch_type                       = "FARGATE"
  health_check_grace_period_seconds = 60
  enable_execute_command            = false # sin shell en producción

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = var.target_group_arn
    container_name   = "signer"
    container_port   = var.container_port
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  tags = var.tags
}

# ------------------------------------------------------------- Autoescalado --
resource "aws_appautoscaling_target" "signer" {
  max_capacity       = var.max_capacity
  min_capacity       = var.desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.signer.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "signer_cpu" {
  name               = "${local.name}-cpu-target"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.signer.resource_id
  scalable_dimension = aws_appautoscaling_target.signer.scalable_dimension
  service_namespace  = aws_appautoscaling_target.signer.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = 60
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    scale_in_cooldown  = 300
    scale_out_cooldown = 60
  }
}
