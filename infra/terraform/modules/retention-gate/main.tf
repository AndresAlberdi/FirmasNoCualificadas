###############################################################################
# Módulo: retention-gate
#
# Compuerta que detiene el `plan` si la infraestructura incumpliría el plazo de
# conservación de la jurisdicción activa, o si el perfil de esa jurisdicción no
# cuenta con validación legal (ADR-0006, ADR-0008; regla inviolable 11).
#
# POR QUÉ ES UN MÓDULO Y NO UNA VALIDACIÓN SUELTA
#
# 1. `validation` en una variable no puede comparar dos variables entre sí, que
#    es justamente lo que hace falta acá.
# 2. Aislado del proveedor de AWS, se puede probar con `terraform test` sin
#    credenciales y sin simular la nube: la compuerta tiene pruebas propias, y
#    una precondición que nadie ejercita puede haberse roto sin que nadie lo note.
# 3. Cada entorno la invoca con sus valores, sin duplicar la lógica.
#
# POR QUÉ FALLA EN `plan` Y NO EN `apply`
#
# En modo COMPLIANCE la retención de S3 Object Lock es irreversible: no puede
# acortarse ni siquiera por el usuario raíz de la cuenta. Un valor equivocado no
# se corrige, se hereda durante todo el plazo, y arreglarlo exige reconstruir el
# bucket y migrar la evidencia.
###############################################################################

resource "terraform_data" "gate" {
  input = {
    jurisdiccion = var.jurisdiction_code
    configurado  = var.configured_retention_days
    minimo       = var.jurisdiction_minimum_retention_days
    entorno      = var.environment
  }

  lifecycle {
    precondition {
      condition = var.configured_retention_days >= var.jurisdiction_minimum_retention_days
      error_message = format(
        "Conservación insuficiente: %d días configurados frente al mínimo de %d que exige %s (%s). En modo COMPLIANCE la retención es irreversible: corríjalo antes de aplicar.",
        var.configured_retention_days,
        var.jurisdiction_minimum_retention_days,
        var.jurisdiction_name,
        var.jurisdiction_retention_legal_basis,
      )
    }

    # Un perfil sin revisión de asesoría legal local sirve para comprobar que la
    # arquitectura generaliza; sostener con él un entorno real produciría
    # constancias que citan una norma que nadie verificó.
    precondition {
      condition = var.jurisdiction_legally_validated || var.environment == "dev"
      error_message = format(
        "El perfil de %s no cuenta con validación legal y no puede sostener el entorno %s. Vea T-02 en docs/PENDIENTES.md.",
        var.jurisdiction_name,
        var.environment,
      )
    }
  }
}
