#!/usr/bin/env bash
#
# Crea el backend de estado remoto de Terraform en la cuenta de gestión.
# Se ejecuta UNA sola vez por cuenta. Es idempotente: si los recursos ya
# existen, informa y termina sin modificarlos.
#
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
PROFILE="${AWS_PROFILE:-}"
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text ${PROFILE:+--profile "$PROFILE"})"
BUCKET="pscnc-tfstate-${ACCOUNT_ID}"
TABLE="pscnc-tfstate-lock"

aws_cmd() { aws "$@" --region "$REGION" ${PROFILE:+--profile "$PROFILE"}; }

echo "Cuenta: ${ACCOUNT_ID} · Región: ${REGION}"

if aws_cmd s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  echo "El bucket ${BUCKET} ya existe; no se modifica."
else
  echo "Creando bucket de estado ${BUCKET}..."
  if [ "$REGION" = "us-east-1" ]; then
    aws_cmd s3api create-bucket --bucket "$BUCKET"
  else
    aws_cmd s3api create-bucket --bucket "$BUCKET" \
      --create-bucket-configuration "LocationConstraint=${REGION}"
  fi

  aws_cmd s3api put-bucket-versioning --bucket "$BUCKET" \
    --versioning-configuration Status=Enabled

  aws_cmd s3api put-bucket-encryption --bucket "$BUCKET" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"aws:kms"},"BucketKeyEnabled":true}]}'

  aws_cmd s3api put-public-access-block --bucket "$BUCKET" \
    --public-access-block-configuration \
    'BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true'
fi

if aws_cmd dynamodb describe-table --table-name "$TABLE" >/dev/null 2>&1; then
  echo "La tabla de bloqueo ${TABLE} ya existe; no se modifica."
else
  echo "Creando tabla de bloqueo ${TABLE}..."
  aws_cmd dynamodb create-table \
    --table-name "$TABLE" \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema AttributeName=LockID,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws_cmd dynamodb wait table-exists --table-name "$TABLE"
fi

cat <<EOF

Backend listo. Complete backend.hcl con:

  bucket         = "${BUCKET}"
  region         = "${REGION}"
  dynamodb_table = "${TABLE}"

EOF
