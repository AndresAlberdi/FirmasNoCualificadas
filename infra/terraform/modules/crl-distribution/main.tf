###############################################################################
# Módulo: crl-distribution
#
# Publicación de la Lista de Revocación de Certificados (CRL) de la CA
# intermedia. Aunque los certificados de firmante son efímeros, los validadores
# de PDF exigen un punto de distribución alcanzable y vigente para la CA.
#
# La CRL se regenera diariamente aunque no haya revocaciones: una CRL con
# nextUpdate vencido es interpretada como fallo de validación por Adobe Acrobat.
###############################################################################

locals {
  name = "pscnc-crl-${var.environment}"
}

resource "aws_s3_bucket" "crl" {
  bucket = var.crl_bucket_name
  tags = merge(var.tags, {
    Name      = var.crl_bucket_name
    DataClass = "public"
  })
}

# La CRL es contenido público y firmado, de modo que el cifrado no protege su
# confidencialidad: protege su integridad en reposo frente a una escritura que
# no pase por la política de la clave. Una CRL alterada haría que un validador
# aceptara certificados revocados.
resource "aws_s3_bucket_server_side_encryption_configuration" "crl" {
  bucket = aws_s3_bucket.crl.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_evidence_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "crl" {
  bucket                  = aws_s3_bucket.crl.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "crl" {
  bucket = aws_s3_bucket.crl.id
  versioning_configuration {
    status = "Enabled"
  }
}

# --------------------------------------------------------------- CloudFront --
resource "aws_cloudfront_origin_access_control" "crl" {
  name                              = "${local.name}-oac"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "crl" {
  enabled         = true
  comment         = "Distribucion de CRL del PSCNC (${var.environment})"
  is_ipv6_enabled = true
  price_class     = "PriceClass_100"
  aliases         = var.crl_domain_name == null ? [] : [var.crl_domain_name]

  origin {
    domain_name              = aws_s3_bucket.crl.bucket_regional_domain_name
    origin_id                = "crl-s3-origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.crl.id
  }

  default_cache_behavior {
    target_origin_id       = "crl-s3-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true

    # TTL corto: una CRL revocada de emergencia debe propagarse en minutos.
    min_ttl     = 0
    default_ttl = var.crl_cache_ttl_seconds
    max_ttl     = var.crl_cache_ttl_seconds

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = var.crl_certificate_arn == null
    acm_certificate_arn            = var.crl_certificate_arn
    ssl_support_method             = var.crl_certificate_arn == null ? null : "sni-only"
    minimum_protocol_version       = var.crl_certificate_arn == null ? null : "TLSv1.2_2021"
  }

  tags = var.tags
}

data "aws_iam_policy_document" "crl_bucket" {
  statement {
    sid    = "AllowCloudFrontOacRead"
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.crl.arn}/*"]
    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.crl.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "crl" {
  bucket = aws_s3_bucket.crl.id
  policy = data.aws_iam_policy_document.crl_bucket.json
}

# ------------------------------------------------- Lambda de regeneración ----
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect = "Allow"
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
    actions = ["sts:AssumeRole"]
  }
}

resource "aws_iam_role" "crl_publisher" {
  name               = "${local.name}-publisher-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
  tags               = var.tags
}

data "aws_iam_policy_document" "crl_publisher" {
  statement {
    effect    = "Allow"
    actions   = ["kms:Sign", "kms:GetPublicKey", "kms:DescribeKey"]
    resources = [var.kms_ca_key_arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.crl.arn}/*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["cloudfront:CreateInvalidation"]
    resources = [aws_cloudfront_distribution.crl.arn]
  }
  statement {
    effect    = "Allow"
    actions   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["arn:aws:logs:*:*:*"]
  }
  statement {
    effect    = "Allow"
    actions   = ["sns:Publish"]
    resources = [var.secops_topic_arn]
  }
}

resource "aws_iam_role_policy" "crl_publisher" {
  name   = "${local.name}-publisher-policy"
  role   = aws_iam_role.crl_publisher.id
  policy = data.aws_iam_policy_document.crl_publisher.json
}

resource "aws_lambda_function" "crl_publisher" {
  function_name    = "${local.name}-publisher"
  role             = aws_iam_role.crl_publisher.arn
  handler          = "pscnc.jobs.crl_publisher.handler"
  runtime          = "python3.12"
  architectures    = ["arm64"]
  timeout          = 60
  memory_size      = 512
  filename         = var.lambda_package_path
  source_code_hash = filebase64sha256(var.lambda_package_path)

  # Las variables no llevan secretos, pero sí los identificadores de las claves y
  # los buckets: se cifran con la CMK para que su lectura pase por la política de
  # esa clave, igual que el resto de la infraestructura de evidencia.
  kms_key_arn = var.kms_evidence_key_arn

  # Traza distribuida: cuando una publicación de CRL falla, lo que hace falta es
  # ver dónde, y sin trazas hay que deducirlo de los registros.
  tracing_config {
    mode = "Active"
  }

  # Cola de descarte: una invocación fallida que se pierde deja la CRL vencida
  # sin que nadie se entere, y un validador que no puede comprobar la revocación
  # rechaza la firma.
  dead_letter_config {
    target_arn = aws_sqs_queue.crl_dlq.arn
  }

  # Un pico de invocaciones sobre esta función no debe consumir la concurrencia
  # de la cuenta: publicar la CRL es una tarea programada, no un servicio.
  reserved_concurrent_executions = 2

  environment {
    variables = {
      PSCNC_ENVIRONMENT         = var.environment
      PSCNC_CRYPTO_BACKEND      = "kms"
      PSCNC_KMS_CA_KEY_ID       = var.kms_ca_key_arn
      PSCNC_CRL_BUCKET          = aws_s3_bucket.crl.id
      PSCNC_CRL_OBJECT_KEY      = var.crl_object_key
      PSCNC_CRL_VALIDITY_HOURS  = tostring(var.crl_validity_hours)
      PSCNC_CRL_DISTRIBUTION_ID = aws_cloudfront_distribution.crl.id
      PSCNC_SECOPS_TOPIC_ARN    = var.secops_topic_arn
    }
  }

  tags = var.tags
}

resource "aws_cloudwatch_event_rule" "daily" {
  name                = "${local.name}-daily"
  description         = "Regeneracion diaria de la CRL del PSCNC"
  schedule_expression = var.schedule_expression
  tags                = var.tags
}

resource "aws_cloudwatch_event_target" "daily" {
  rule      = aws_cloudwatch_event_rule.daily.name
  target_id = "crl-publisher"
  arn       = aws_lambda_function.crl_publisher.arn
}

resource "aws_lambda_permission" "events" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.crl_publisher.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.daily.arn
}

# Una CRL que no se regeneró es un incidente: los validadores empezarán a
# rechazar firmas cuando venza nextUpdate.
resource "aws_cloudwatch_metric_alarm" "publisher_failed" {
  alarm_name          = "${local.name}-publisher-failed"
  comparison_operator = "GreaterThanOrEqualToThreshold"
  evaluation_periods  = 1
  metric_name         = "Errors"
  namespace           = "AWS/Lambda"
  period              = 3600
  statistic           = "Sum"
  threshold           = 1
  alarm_description   = "Fallo en la regeneracion de la CRL del PSCNC"
  treat_missing_data  = "notBreaching"
  dimensions = {
    FunctionName = aws_lambda_function.crl_publisher.function_name
  }
  alarm_actions = [var.secops_topic_arn]
  tags          = var.tags
}


###############################################################################
# Cola de descarte de la publicación de CRL
###############################################################################

resource "aws_sqs_queue" "crl_dlq" {
  name = "pscnc-crl-publisher-dlq-${var.environment}"

  # La clave de evidencia: el mensaje descartado lleva el contexto de la
  # invocación fallida.
  kms_master_key_id                 = var.kms_evidence_key_arn
  kms_data_key_reuse_period_seconds = 300

  # Catorce días: tiempo de sobra para que una guardia advierta el fallo y
  # reprocese, sin retener mensajes indefinidamente.
  message_retention_seconds = 1209600

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "crl_dlq_no_vacia" {
  alarm_name          = "pscnc-crl-dlq-${var.environment}"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 300
  statistic           = "Maximum"
  threshold           = 0
  alarm_description   = "La publicación de la CRL falló: un validador que no pueda comprobar la revocación rechazará la firma"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [var.secops_topic_arn]

  dimensions = {
    QueueName = aws_sqs_queue.crl_dlq.name
  }

  tags = var.tags
}
