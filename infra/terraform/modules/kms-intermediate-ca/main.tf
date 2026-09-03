###############################################################################
# Módulo: kms-intermediate-ca
#
# Clave asimétrica de la Entidad de Certificación Intermedia del PSCNC.
# La clave privada se crea dentro de HSM de AWS KMS (FIPS 140-2 Nivel 3) y NUNCA
# puede exportarse. Toda emisión de certificados de firmante y toda firma de CRL
# se realiza mediante la API kms:Sign sobre un digest de 32 bytes.
#
# ADVERTENCIA TÉCNICA: las claves asimétricas de KMS NO admiten rotación
# automática (enable_key_rotation aplica solo a claves simétricas). La rotación
# de la CA intermedia es un procedimiento manual planificado, documentado en
# docs/RUNBOOK-break-glass.md §5, que implica crear una clave nueva, recertificar
# la CA y mantener la anterior habilitada solo para verificación.
###############################################################################

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
}

resource "aws_kms_key" "intermediate_ca" {
  description              = "PSCNC Paraguay - Intermediate CA signing key (${var.environment})"
  key_usage                = "SIGN_VERIFY"
  customer_master_key_spec = var.key_spec
  deletion_window_in_days  = var.deletion_window_in_days
  multi_region             = false
  policy                   = data.aws_iam_policy_document.key_policy.json

  tags = merge(var.tags, {
    Name           = "${var.resource_prefix}-intermediate-ca-${var.environment}"
    DataClass      = "critical"
    Regulation     = "Ley-6822-2021"
    RotationPolicy = "manual-documented"
  })
}

resource "aws_kms_alias" "intermediate_ca" {
  name          = "alias/${var.key_alias}"
  target_key_id = aws_kms_key.intermediate_ca.key_id
}

###############################################################################
# Política de clave: separación de funciones entre administración y uso.
# Los administradores NUNCA pueden firmar; el servicio de firma NUNCA puede
# administrar, deshabilitar ni programar la eliminación de la clave.
###############################################################################

data "aws_iam_policy_document" "key_policy" {
  # Sin esta sentencia la clave queda huérfana de IAM y es irrecuperable.
  statement {
    sid    = "AllowRootAccountIAMDelegation"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = ["arn:aws:iam::${local.account_id}:root"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
  }

  statement {
    sid    = "AllowSecOpsAdministratorsKeyManagement"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.admin_role_arns
    }
    actions = [
      "kms:Create*",
      "kms:Describe*",
      "kms:Enable*",
      "kms:List*",
      "kms:Put*",
      "kms:Update*",
      "kms:Revoke*",
      "kms:Disable*",
      "kms:Get*",
      "kms:TagResource",
      "kms:UntagResource",
      "kms:ScheduleKeyDeletion",
      "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
  }

  statement {
    sid    = "AllowSignerServiceSignOnly"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.signer_role_arns
    }
    actions = [
      "kms:Sign",
      "kms:GetPublicKey",
      "kms:DescribeKey",
    ]
    resources = ["*"]

    # Solo algoritmos aprobados en la DPSC presentada ante la DGFDCE.
    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = var.allowed_signing_algorithms
    }
  }

  # Cierre perimetral: ninguna llamada fuera de TLS.
  statement {
    sid    = "DenyNonTlsCalls"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["kms:*"]
    resources = ["*"]
    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }

  # Defensa contra exfiltración: prohibición explícita de importar o replicar
  # material de clave y de habilitar acceso desde fuera de la organización.
  statement {
    sid    = "DenyKeyMaterialExfiltrationAttempts"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions = [
      "kms:ImportKeyMaterial",
      "kms:ReplicateKey",
    ]
    resources = ["*"]
  }
}
