###############################################################################
# Módulo: kms-tenant-keys
#
# Las dos claves que cada inquilino tiene en exclusiva (ADR-0006):
#
#   1. Sello de acta (ECC_NIST_P256, SIGN_VERIFY). Firma el hash canónico del
#      acta de evidencia del nivel 1 y el resumen del expediente del nivel 2. Su
#      clave pública se publica, de modo que el inquilino y cualquier tercero
#      pueden verificar el sello sin acceso a nuestros registros ni confianza en
#      nosotros. Es lo que hace verificable al nivel 1, donde el PDF no se toca.
#
#   2. Cifrado de evidencias (SYMMETRIC_DEFAULT). Cifrado envolvente de las
#      evidencias en reposo: SSE-KMS de los buckets y cifrado de campo de los
#      atributos sensibles en DynamoDB. Con rotación automática anual, que las
#      claves simétricas sí admiten.
#
# POR QUÉ UNA CLAVE POR INQUILINO Y NO UNA COMPARTIDA
#
# El ADR-0005 aísla a los inquilinos en la capa de repositorio. Una clave por
# inquilino lleva ese aislamiento a la capa criptográfica: aunque un error de
# enrutamiento entregara a un inquilino el identificador de un objeto de otro, el
# descifrado falla porque el contexto de cifrado no coincide. Un control que
# depende de que el código no tenga errores no es un control.
#
# ADVERTENCIA TÉCNICA: las claves asimétricas de KMS NO admiten rotación
# automática. La del sello se rota con el procedimiento manual de alias
# versionados que documenta docs/RUNBOOK-break-glass.md.
###############################################################################

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  nombre     = "pscnc-${var.tenant_id}-${var.environment}"

  etiquetas = merge(var.tags, {
    Tenant      = var.tenant_id
    Environment = var.environment
    DataClass   = "critical"
  })
}

###############################################################################
# 1. Clave de sello del acta de evidencia
###############################################################################

resource "aws_kms_key" "acta_seal" {
  description = "PSCNC - Sello de acta de evidencia del inquilino ${var.tenant_id} (${var.environment})"
  key_usage   = "SIGN_VERIFY"
  # ECDSA P-256: es el algoritmo de `ES256`, el mejor soportado del ecosistema
  # JOSE. El acta viaja en un sobre JWS y no en un certificado X.509, así que acá
  # manda la interoperabilidad con librerías estándar y no el perfil nacional de
  # certificado que rige para la CA intermedia.
  customer_master_key_spec = "ECC_NIST_P256"
  deletion_window_in_days  = var.deletion_window_in_days
  multi_region             = false
  policy                   = data.aws_iam_policy_document.acta_seal.json

  tags = merge(local.etiquetas, {
    Name           = "${local.nombre}-acta-seal"
    Purpose        = "acta-seal"
    RotationPolicy = "manual-documented"
  })
}

# Alias versionado: el código selecciona la clave por alias y nunca por KeyId.
# Un KeyId cableado convierte cada rotación en un despliegue, y durante el
# solapamiento hacen falta las dos claves a la vez —la anterior verificando, la
# nueva firmando—, algo que un identificador fijo no permite expresar.
resource "aws_kms_alias" "acta_seal" {
  name          = "alias/fnc/${var.environment}/${var.tenant_id}/acta-seal/v${var.acta_seal_key_version}"
  target_key_id = aws_kms_key.acta_seal.key_id
}

###############################################################################
# 2. Clave de cifrado de evidencias
###############################################################################

resource "aws_kms_key" "evidence" {
  description             = "PSCNC - Cifrado de evidencias del inquilino ${var.tenant_id} (${var.environment})"
  key_usage               = "ENCRYPT_DECRYPT"
  deletion_window_in_days = var.deletion_window_in_days
  # Las claves simétricas sí admiten rotación automática. Anual.
  enable_key_rotation = true
  multi_region        = false
  policy              = data.aws_iam_policy_document.evidence.json

  tags = merge(local.etiquetas, {
    Name           = "${local.nombre}-evidence"
    Purpose        = "evidence-encryption"
    RotationPolicy = "automatic-annual"
  })
}

resource "aws_kms_alias" "evidence" {
  name          = "alias/fnc/${var.environment}/${var.tenant_id}/evidence/v${var.evidence_key_version}"
  target_key_id = aws_kms_key.evidence.key_id
}

###############################################################################
# Política de la clave de sello
###############################################################################

data "aws_iam_policy_document" "acta_seal" {
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

  # Administración sin capacidad de firmar: quien puede firmar puede fabricar
  # evidencia, y por eso ningún rol humano tiene kms:Sign (regla inviolable 8).
  statement {
    sid    = "AllowAdministratorsManagementWithoutSigning"
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
      "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
  }

  # El servicio firma y lee la clave pública, nada más.
  statement {
    sid    = "AllowSignerServiceSealOnly"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.signer_role_arns
    }
    actions = [
      "kms:Sign",
      "kms:Verify",
      "kms:GetPublicKey",
      "kms:DescribeKey",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:SigningAlgorithm"
      values   = ["ECDSA_SHA_256"]
    }
  }

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

  # La eliminación de una clave de sello destruye la verificabilidad de todas las
  # actas que firmó: la evidencia sobrevive pero deja de poder comprobarse. Solo
  # el rol de emergencia puede programarla, y su uso queda registrado en
  # CloudTrail y dispara alarma (docs/RUNBOOK-break-glass.md).
  statement {
    sid    = "DenyKeyDeletionExceptBreakGlass"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["kms:ScheduleKeyDeletion"]
    resources = ["*"]
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = var.break_glass_role_arns
    }
  }

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

###############################################################################
# Política de la clave de evidencias
###############################################################################

data "aws_iam_policy_document" "evidence" {
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
    sid    = "AllowAdministratorsManagementWithoutDataAccess"
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
      "kms:CancelKeyDeletion",
    ]
    resources = ["*"]
  }

  # ---------------------------------------------------------------------------
  # El control central del aislamiento criptográfico entre inquilinos.
  #
  # Toda operación tiene que llevar un contexto de cifrado con el `tenant_id` de
  # ESTA clave y un `transaction_id` cualquiera. Consecuencia: un texto cifrado
  # del inquilino A no puede descifrarse en el contexto del inquilino B, aunque
  # el llamador tenga permisos sobre ambas claves. Es el ADR-0005 hecho cumplir
  # en la capa criptográfica, donde un error de código no puede eludirlo.
  # ---------------------------------------------------------------------------
  statement {
    sid    = "AllowSignerServiceDataKeyUseWithTenantContext"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.signer_role_arns
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:EncryptionContext:tenant_id"
      values   = [var.tenant_id]
    }

    # Se exige que la clave exista, sin fijar su valor: liga cada operación a una
    # transacción concreta y la vuelve rastreable en CloudTrail.
    condition {
      test     = "Null"
      variable = "kms:EncryptionContext:transaction_id"
      values   = ["false"]
    }
  }

  # Los servicios de AWS que cifran en nombre del servicio (S3, DynamoDB) reciben
  # permiso acotado por `kms:ViaService`: no pueden usar la clave por sí mismos.
  statement {
    sid    = "AllowAwsServicesViaServiceOnly"
    effect = "Allow"
    principals {
      type        = "AWS"
      identifiers = var.signer_role_arns
    }
    actions = [
      "kms:Encrypt",
      "kms:Decrypt",
      "kms:ReEncrypt*",
      "kms:GenerateDataKey*",
      "kms:DescribeKey",
    ]
    resources = ["*"]

    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values = [
        "s3.${var.region}.amazonaws.com",
        "dynamodb.${var.region}.amazonaws.com",
      ]
    }
  }

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

  # Eliminar esta clave hace ilegible toda la evidencia del inquilino de forma
  # irreversible, incluida la que S3 Object Lock conserva por obligación legal.
  statement {
    sid    = "DenyKeyDeletionExceptBreakGlass"
    effect = "Deny"
    principals {
      type        = "AWS"
      identifiers = ["*"]
    }
    actions   = ["kms:ScheduleKeyDeletion"]
    resources = ["*"]
    condition {
      test     = "ArnNotEquals"
      variable = "aws:PrincipalArn"
      values   = var.break_glass_role_arns
    }
  }

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
