output "verified_retention_days" {
  description = <<-EOT
    La retención ya comprobada contra el mínimo de la jurisdicción. Los módulos
    que crean buckets con Object Lock deben tomar el valor de acá y no de la
    variable directa: así la compuerta queda en el camino de la dependencia y no
    puede saltearse por olvido.
  EOT
  value       = var.configured_retention_days
  depends_on  = [terraform_data.gate]
}
