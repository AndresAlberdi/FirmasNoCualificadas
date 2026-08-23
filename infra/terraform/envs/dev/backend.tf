###############################################################################
# Estado remoto. El bucket y la tabla de bloqueo viven en la cuenta de gestión,
# separada de las cuentas de carga de trabajo, y se crean una única vez fuera
# de este stack (scripts/bootstrap-tfstate.sh).
#
# Complete los valores mediante:
#   terraform init -backend-config=backend.hcl
###############################################################################

terraform {
  backend "s3" {
    key          = "fenc-py/dev/terraform.tfstate"
    encrypt      = true
    use_lockfile = true
    # bucket, region, dynamodb_table y kms_key_id se pasan por -backend-config
  }
}
