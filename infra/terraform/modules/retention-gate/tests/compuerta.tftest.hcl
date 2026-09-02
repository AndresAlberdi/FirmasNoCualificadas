# Pruebas de la compuerta de conservación.
#
# No necesitan credenciales ni proveedor de nube: el módulo usa solo recursos
# integrados, precisamente para que su comportamiento pueda comprobarse.
#
# Ejecutar con:  make tf-test

variables {
  jurisdiction_code                   = "PY"
  jurisdiction_name                   = "República del Paraguay"
  jurisdiction_minimum_retention_days = 1095
  jurisdiction_retention_legal_basis  = "Res. SS.SG. N.º 210/2025, art. 9"
  jurisdiction_legally_validated      = true
  environment                         = "prod"
  configured_retention_days           = 1095
}

# --------------------------------------------------------------------------- #
run "la_retencion_igual_al_minimo_pasa" {
  command = plan

  assert {
    condition     = output.verified_retention_days == 1095
    error_message = "La compuerta debería dejar pasar una retención igual al mínimo."
  }
}

# --------------------------------------------------------------------------- #
run "una_retencion_mayor_al_minimo_pasa" {
  command = plan

  variables {
    configured_retention_days = 2555
  }

  assert {
    condition     = output.verified_retention_days == 2555
    error_message = "Conservar de más nunca invalida evidencia: debe admitirse."
  }
}

# --------------------------------------------------------------------------- #
run "el_plazo_nominal_de_dos_anios_no_alcanza" {
  command = plan

  variables {
    # El error que esta compuerta existe para atrapar: confundir los dos años que
    # la norma cuenta desde el vencimiento del contrato con el plazo que se fija
    # sobre el objeto, que se escribe al firmarse. A ojo, en una revisión, 730
    # parece correcto porque coincide con la cifra de la norma.
    configured_retention_days = 730
  }

  expect_failures = [
    terraform_data.gate,
  ]
}

# --------------------------------------------------------------------------- #
run "una_retencion_de_un_dia_menos_tambien_bloquea" {
  command = plan

  variables {
    configured_retention_days = 1094
  }

  expect_failures = [
    terraform_data.gate,
  ]
}

# --------------------------------------------------------------------------- #
run "una_jurisdiccion_sin_validacion_legal_no_sostiene_produccion" {
  command = plan

  variables {
    jurisdiction_code              = "BO"
    jurisdiction_name              = "Estado Plurinacional de Bolivia"
    jurisdiction_legally_validated = false
    environment                    = "prod"
  }

  expect_failures = [
    terraform_data.gate,
  ]
}

# --------------------------------------------------------------------------- #
run "una_jurisdiccion_sin_validacion_legal_tampoco_sostiene_staging" {
  command = plan

  variables {
    jurisdiction_code              = "BO"
    jurisdiction_name              = "Estado Plurinacional de Bolivia"
    jurisdiction_legally_validated = false
    environment                    = "staging"
  }

  expect_failures = [
    terraform_data.gate,
  ]
}

# --------------------------------------------------------------------------- #
run "en_desarrollo_si_se_admite_una_jurisdiccion_sin_validar" {
  command = plan

  variables {
    jurisdiction_code              = "BO"
    jurisdiction_name              = "Estado Plurinacional de Bolivia"
    jurisdiction_legally_validated = false
    environment                    = "dev"
  }

  assert {
    condition     = output.verified_retention_days == 1095
    error_message = "En desarrollo debe poder probarse la generalización a otra jurisdicción."
  }
}
