###############################################################################
# Módulo: audit-trail-dynamodb
#
# Tabla única (single-table design) de la pista de auditoría forense.
# Ver ADR-0003: DynamoDB es el índice operativo; la copia con valor probatorio
# es el espejo WORM en S3 alimentado por Streams.
###############################################################################

resource "aws_dynamodb_table" "audit_trail" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
  attribute {
    name = "GSI1PK"
    type = "S"
  }
  attribute {
    name = "GSI1SK"
    type = "S"
  }
  attribute {
    name = "GSI2PK"
    type = "S"
  }
  attribute {
    name = "GSI2SK"
    type = "S"
  }

  # Correlación de todas las firmas de un ciudadano (uso pericial).
  global_secondary_index {
    name            = "GSI1-Signer"
    hash_key        = "GSI1PK"
    range_key       = "GSI1SK"
    projection_type = "ALL"
  }

  # Aislamiento y reporte por cliente B2B (ADR-0005).
  global_secondary_index {
    name            = "GSI2-Tenant"
    hash_key        = "GSI2PK"
    range_key       = "GSI2SK"
    projection_type = "ALL"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  # Alimenta la replicación hacia el bucket WORM de evidencias.
  stream_enabled   = true
  stream_view_type = "NEW_AND_OLD_IMAGES"

  # La evidencia no expira antes del plazo legal: la protección contra borrado
  # accidental del recurso es obligatoria en todos los entornos.
  deletion_protection_enabled = true

  tags = merge(var.tags, {
    Name       = var.table_name
    DataClass  = "critical"
    Regulation = "Ley-6822-2021"
  })
}

###############################################################################
# Tabla de auditoría de accesos del panel B2B (quién reveló qué PII y cuándo).
###############################################################################

resource "aws_dynamodb_table" "dashboard_audit_log" {
  name         = var.dashboard_audit_table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  point_in_time_recovery {
    enabled = true
  }

  deletion_protection_enabled = true

  tags = merge(var.tags, {
    Name      = var.dashboard_audit_table_name
    DataClass = "sensitive"
  })
}
