###############################################################################
# Módulo: idempotency-dynamodb
#
# Tabla dedicada a los registros de idempotencia del contrato público (T-11).
#
# POR QUÉ UNA TABLA PROPIA Y NO LA DE AUDITORÍA
#
# La pista de auditoría no puede expirar: su plazo de conservación es una
# obligación legal y el ADR-0003 la protege incluso frente al usuario raíz. Los
# registros de idempotencia sí deben expirar, porque retenerlos indefinidamente
# convertiría el almacén en un registro paralelo de toda la actividad.
#
# Habilitar TTL sobre la tabla de auditoría para cubrir el segundo caso pondría
# un mecanismo de borrado automático en la misma tabla que guarda lo que no puede
# borrarse. Bastaría que un ítem de evidencia recibiera por error el atributo de
# expiración para que DynamoDB lo eliminara en silencio, sin registro y sin forma
# de recuperarlo. La separación elimina esa clase de error, y cuesta una tabla.
###############################################################################

resource "aws_dynamodb_table" "idempotency" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"

  attribute {
    name = "PK"
    type = "S"
  }

  # Expiración nativa. No es inmediata —DynamoDB puede tardar hasta 48 horas—,
  # pero el control comprueba la ventana al leer y descarta lo vencido aunque
  # siga almacenado: el TTL solo evita que la tabla crezca sin límite.
  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  server_side_encryption {
    enabled = true
    # Misma clave que la evidencia: el cuerpo guardado incluye la respuesta
    # completa de la operación, con los puntajes biométricos que el tenant
    # declaró.
    kms_key_arn = var.kms_key_arn
  }

  # Sin recuperación a un punto en el tiempo ni protección contra borrado: a
  # diferencia de la evidencia, perder estos registros no destruye una prueba.
  # Lo peor que produce es que un reintento se ejecute dos veces, y para eso la
  # transacción ya rechaza una segunda confirmación.
  point_in_time_recovery {
    enabled = false
  }

  tags = merge(var.tags, {
    Name      = var.table_name
    DataClass = "operational"
    Purpose   = "idempotency"
  })
}
