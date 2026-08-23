###############################################################################
# Módulo: evidence-vault-s3
#
# Dos repositorios documentales:
#   - signed-vault    : PDFs firmados entregables al cliente B2B.
#   - evidence-trail  : expedientes de evidencia con Object Lock en modo
#                       COMPLIANCE. En ese modo ningún principal —ni el usuario
#                       raíz de la cuenta— puede borrar el objeto ni acortar su
#                       retención antes del vencimiento. Es la propiedad que
#                       sostiene el valor probatorio (ADR-0003).
#
# ADVERTENCIA OPERATIVA: Object Lock solo puede habilitarse en la CREACIÓN del
# bucket. Un bucket creado sin él exige migración completa. Verifique el valor
# de object_lock_retention_days antes del primer apply: los objetos escritos
# quedarán retenidos ese plazo de forma irreversible.
###############################################################################

# --------------------------------------------------------- Bóveda de firmados
resource "aws_s3_bucket" "signed_vault" {
  bucket = var.signed_bucket_name

  tags = merge(var.tags, {
    Name      = var.signed_bucket_name
    DataClass = "confidential"
  })
}

resource "aws_s3_bucket_public_access_block" "signed_vault" {
  bucket                  = aws_s3_bucket.signed_vault.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "signed_vault" {
  bucket = aws_s3_bucket.signed_vault.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "signed_vault" {
  bucket = aws_s3_bucket.signed_vault.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "signed_vault" {
  bucket = aws_s3_bucket.signed_vault.id

  rule {
    id     = "transicion-a-almacenamiento-frio"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
    noncurrent_version_expiration {
      noncurrent_days = var.signed_noncurrent_expiration_days
    }
  }
}

# -------------------------------------------------- Bóveda WORM de evidencias
resource "aws_s3_bucket" "evidence_trail" {
  bucket              = var.evidence_bucket_name
  object_lock_enabled = true

  tags = merge(var.tags, {
    Name       = var.evidence_bucket_name
    DataClass  = "critical"
    Regulation = "Ley-6822-2021"
    WORM       = "compliance"
  })
}

resource "aws_s3_bucket_public_access_block" "evidence_trail" {
  bucket                  = aws_s3_bucket.evidence_trail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Object Lock exige versionado habilitado.
resource "aws_s3_bucket_versioning" "evidence_trail" {
  bucket = aws_s3_bucket.evidence_trail.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_object_lock_configuration" "evidence_trail" {
  bucket = aws_s3_bucket.evidence_trail.id

  rule {
    default_retention {
      mode = "COMPLIANCE"
      days = var.object_lock_retention_days
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "evidence_trail" {
  bucket = aws_s3_bucket.evidence_trail.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "evidence_trail" {
  bucket = aws_s3_bucket.evidence_trail.id

  rule {
    id     = "transicion-a-almacenamiento-frio"
    status = "Enabled"
    filter {}
    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }
  }
}

# Registro de todos los accesos a la bóveda de evidencias.
resource "aws_s3_bucket_logging" "evidence_trail" {
  count         = var.access_log_bucket == null ? 0 : 1
  bucket        = aws_s3_bucket.evidence_trail.id
  target_bucket = var.access_log_bucket
  target_prefix = "s3-access/evidence-trail/"
}

# ------------------------------------------------------- Políticas de bucket
data "aws_iam_policy_document" "evidence_trail" {
  statement {
    sid    = "DenyNonTlsAccess"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.evidence_trail.arn,
      "${aws_s3_bucket.evidence_trail.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  statement {
    sid    = "DenyUnencryptedObjectUploads"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.evidence_trail.arn}/*"]
    condition {
      test     = "StringNotEquals"
      variable = "s3:x-amz-server-side-encryption"
      values   = ["aws:kms"]
    }
  }

  # Defensa en profundidad: aunque el modo COMPLIANCE ya lo impide, se niega de
  # forma explícita cualquier intento de relajar la retención o el modo legal.
  statement {
    sid    = "DenyObjectLockDowngrade"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = [
      "s3:PutObjectRetention",
      "s3:BypassGovernanceRetention",
      "s3:PutBucketObjectLockConfiguration",
    ]
    resources = [
      aws_s3_bucket.evidence_trail.arn,
      "${aws_s3_bucket.evidence_trail.arn}/*",
    ]
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = var.object_lock_admin_role_arns
    }
  }
}

resource "aws_s3_bucket_policy" "evidence_trail" {
  bucket = aws_s3_bucket.evidence_trail.id
  policy = data.aws_iam_policy_document.evidence_trail.json
}

data "aws_iam_policy_document" "signed_vault" {
  statement {
    sid    = "DenyNonTlsAccess"
    effect = "Deny"
    principals {
      type        = "*"
      identifiers = ["*"]
    }
    actions = ["s3:*"]
    resources = [
      aws_s3_bucket.signed_vault.arn,
      "${aws_s3_bucket.signed_vault.arn}/*",
    ]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "signed_vault" {
  bucket = aws_s3_bucket.signed_vault.id
  policy = data.aws_iam_policy_document.signed_vault.json
}
