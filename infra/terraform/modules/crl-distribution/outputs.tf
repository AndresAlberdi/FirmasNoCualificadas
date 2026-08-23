output "crl_bucket_name" {
  description = "Bucket que almacena la CRL."
  value       = aws_s3_bucket.crl.id
}

output "crl_distribution_domain" {
  description = "Dominio de CloudFront que sirve la CRL."
  value       = aws_cloudfront_distribution.crl.domain_name
}

output "crl_public_url" {
  description = "URL pública de la CRL, a declarar en el perfil de certificados y en la DPSC."
  value       = "https://${coalesce(var.crl_domain_name, aws_cloudfront_distribution.crl.domain_name)}/${var.crl_object_key}"
}

output "publisher_function_name" {
  description = "Nombre de la función que regenera la CRL."
  value       = aws_lambda_function.crl_publisher.function_name
}
