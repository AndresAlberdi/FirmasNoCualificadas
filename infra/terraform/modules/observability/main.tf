###############################################################################
# Módulo: observability
#
# Trazabilidad regulatoria: CloudTrail con validación de integridad del log,
# GuardDuty, y alarmas sobre el uso de la clave de la CA. El objetivo no es
# operativo sino probatorio: demostrar ante la DGFDCE que toda operación
# criptográfica quedó registrada de forma verificable.
###############################################################################

locals {
  name = "pscnc-obs-${var.environment}"
}

# ------------------------------------------------------ Canal de alertas -----
resource "aws_sns_topic" "secops" {
  name              = "${local.name}-secops"
  kms_master_key_id = var.kms_key_arn
  tags              = var.tags
}

resource "aws_sns_topic_subscription" "secops_email" {
  for_each  = toset(var.secops_email_endpoints)
  topic_arn = aws_sns_topic.secops.arn
  protocol  = "email"
  endpoint  = each.value
}

# ---------------------------------------------------------- CloudTrail -------
resource "aws_s3_bucket" "trail" {
  bucket = var.trail_bucket_name
  tags = merge(var.tags, {
    Name      = var.trail_bucket_name
    DataClass = "critical"
  })
}

# El bucket guarda el registro de todas las operaciones de KMS, que es lo que
# hace auditable una firma (ADR-0006): una firma sin su traza en CloudTrail no
# es verificable. Se cifra con la clave gestionada por el cliente, no con la
# clave de servicio de AWS, para que el acceso quede sujeto a la política de esa
# clave y quede registrado a su vez.
resource "aws_s3_bucket_server_side_encryption_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    # Reduce el costo y la latencia de las llamadas a KMS reutilizando la clave
    # de datos dentro de un mismo contexto de cifrado.
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "trail" {
  bucket                  = aws_s3_bucket.trail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "trail" {
  bucket = aws_s3_bucket.trail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "trail" {
  bucket = aws_s3_bucket.trail.id
  rule {
    id     = "retencion-regulatoria"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    expiration {
      days = var.trail_retention_days
    }
  }
}

data "aws_iam_policy_document" "trail_bucket" {
  statement {
    sid    = "AWSCloudTrailAclCheck"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:GetBucketAcl"]
    resources = [aws_s3_bucket.trail.arn]
  }

  statement {
    sid    = "AWSCloudTrailWrite"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.trail.arn}/AWSLogs/${var.account_id}/*"]
    condition {
      test     = "StringEquals"
      variable = "s3:x-amz-acl"
      values   = ["bucket-owner-full-control"]
    }
  }
}

resource "aws_s3_bucket_policy" "trail" {
  bucket = aws_s3_bucket.trail.id
  policy = data.aws_iam_policy_document.trail_bucket.json
}

# El grupo de logs recibe los eventos de CloudTrail, incluidas todas las
# operaciones de KMS: es la traza que hace auditable una firma. Se cifra con la
# clave gestionada por el cliente para que su lectura quede sujeta a la política
# de esa clave, igual que el bucket del espejo.
resource "aws_cloudwatch_log_group" "trail" {
  kms_key_id        = var.kms_key_arn
  name              = "/aws/cloudtrail/${local.name}"
  retention_in_days = var.log_retention_days
  tags              = var.tags
}

data "aws_iam_policy_document" "trail_logs_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudtrail.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "trail_logs" {
  name               = "${local.name}-trail-to-logs"
  assume_role_policy = data.aws_iam_policy_document.trail_logs_assume.json
  tags               = var.tags
}

resource "aws_iam_role_policy" "trail_logs" {
  name = "${local.name}-trail-to-logs"
  role = aws_iam_role.trail_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
      Resource = "${aws_cloudwatch_log_group.trail.arn}:*"
    }]
  })
}

resource "aws_cloudtrail" "main" {
  name                          = local.name
  s3_bucket_name                = aws_s3_bucket.trail.id
  include_global_service_events = true
  is_multi_region_trail         = true
  enable_log_file_validation    = true # firma digital de los archivos de log
  kms_key_id                    = var.kms_key_arn

  cloud_watch_logs_group_arn = "${aws_cloudwatch_log_group.trail.arn}:*"
  cloud_watch_logs_role_arn  = aws_iam_role.trail_logs.arn

  # Registro de operaciones sobre los datos de evidencia.
  advanced_event_selector {
    name = "Operaciones de datos en buckets de evidencia"
    field_selector {
      field  = "eventCategory"
      equals = ["Data"]
    }
    field_selector {
      field  = "resources.type"
      equals = ["AWS::S3::Object"]
    }
    field_selector {
      field       = "resources.ARN"
      starts_with = var.data_event_bucket_arns
    }
  }

  advanced_event_selector {
    name = "Eventos de gestion"
    field_selector {
      field  = "eventCategory"
      equals = ["Management"]
    }
  }

  depends_on = [aws_s3_bucket_policy.trail]
  tags       = var.tags
}

# ----------------------------------------------------------- GuardDuty ------
resource "aws_guardduty_detector" "main" {
  count                        = var.enable_guardduty ? 1 : 0
  enable                       = true
  finding_publishing_frequency = "FIFTEEN_MINUTES"
  tags                         = var.tags
}

# ------------------------------------- Alarmas sobre el uso de la CA ---------
resource "aws_cloudwatch_log_metric_filter" "kms_sign" {
  name           = "${local.name}-kms-sign"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"kms.amazonaws.com\") && ($.eventName = \"Sign\") }"

  metric_transformation {
    name      = "PscncKmsSignCalls"
    namespace = "PSCNC/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "kms_sign_anomaly" {
  alarm_name          = "pscnc-kms-sign-anomaly-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "PscncKmsSignCalls"
  namespace           = "PSCNC/Security"
  period              = 300
  statistic           = "Sum"
  threshold           = var.kms_sign_alarm_threshold
  alarm_description   = "Volumen anomalo de firmas con la CA intermedia: posible compromiso (ver RUNBOOK-break-glass)"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.secops.arn]
  tags                = var.tags
}

# Uso de la CA por un principal distinto del servicio de firma: SEV-1 inmediato.
resource "aws_cloudwatch_log_metric_filter" "kms_sign_unexpected_principal" {
  name           = "${local.name}-kms-sign-unexpected-principal"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"kms.amazonaws.com\") && ($.eventName = \"Sign\") && ($.userIdentity.sessionContext.sessionIssuer.userName != \"${var.expected_signer_role_name}\") }"

  metric_transformation {
    name      = "PscncKmsSignUnexpectedPrincipal"
    namespace = "PSCNC/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "kms_sign_unexpected_principal" {
  alarm_name          = "pscnc-kms-sign-unexpected-principal-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PscncKmsSignUnexpectedPrincipal"
  namespace           = "PSCNC/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "SEV-1: kms:Sign invocado por un principal no autorizado sobre la CA intermedia"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.secops.arn]
  tags                = var.tags
}

###############################################################################
# Deshabilitación o eliminación de una clave: SEV-1 inmediato.
#
# Deshabilitar la clave de la CA detiene toda emisión de certificados; eliminar
# una clave de sello destruye la verificabilidad de cada acta que firmó, y
# eliminar una de evidencias hace ilegible evidencia con obligación legal de
# conservación. Las tres operaciones son legítimas dentro del procedimiento de
# emergencia (docs/RUNBOOK-break-glass.md) y ninguna debería ocurrir fuera de él,
# así que la alarma se dispara con una sola aparición.
###############################################################################

resource "aws_cloudwatch_log_metric_filter" "kms_key_lifecycle" {
  name           = "${local.name}-kms-key-lifecycle"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"kms.amazonaws.com\") && (($.eventName = \"DisableKey\") || ($.eventName = \"ScheduleKeyDeletion\") || ($.eventName = \"DeleteAlias\") || ($.eventName = \"PutKeyPolicy\")) }"

  metric_transformation {
    name      = "PscncKmsKeyLifecycleEvents"
    namespace = "PSCNC/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "kms_key_lifecycle" {
  alarm_name          = "pscnc-kms-key-lifecycle-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PscncKmsKeyLifecycleEvents"
  namespace           = "PSCNC/Security"
  period              = 60
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "SEV-1: se deshabilitó, se programó la eliminación o se alteró la política de una clave de KMS"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.secops.arn]
  tags                = var.tags
}

# Descifrado rechazado por contexto: puede ser un error de enrutamiento entre
# inquilinos, o un intento de acceso cruzado. En ambos casos hay que mirarlo.
resource "aws_cloudwatch_log_metric_filter" "kms_context_mismatch" {
  name           = "${local.name}-kms-context-mismatch"
  log_group_name = aws_cloudwatch_log_group.trail.name
  pattern        = "{ ($.eventSource = \"kms.amazonaws.com\") && ($.eventName = \"Decrypt\") && ($.errorCode = \"InvalidCiphertextException\") }"

  metric_transformation {
    name      = "PscncKmsContextMismatch"
    namespace = "PSCNC/Security"
    value     = "1"
  }
}

resource "aws_cloudwatch_metric_alarm" "kms_context_mismatch" {
  alarm_name          = "pscnc-kms-context-mismatch-${var.environment}"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "PscncKmsContextMismatch"
  namespace           = "PSCNC/Security"
  period              = 300
  statistic           = "Sum"
  threshold           = var.kms_context_mismatch_threshold
  alarm_description   = "Descifrado rechazado por contexto: posible acceso cruzado entre inquilinos (ADR-0005)"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.secops.arn]
  tags                = var.tags
}
