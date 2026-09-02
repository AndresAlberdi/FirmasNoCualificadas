#!/usr/bin/env bash
# ==============================================================================
# oci-token-exchange.sh — Federación OIDC GitHub Actions → OCI (sin API keys)
# ==============================================================================
# Versión: 2.0 | Fecha: 2026-08-24
# Documentos relacionados: 01-seguridad/02-identidad-federada-oidc.md (sección 3),
#   02-pipelines/workflows/ci-oci-terraform.yml, 03-scripts/bootstrap-repo.sh
#   (lo copia a .github/scripts/ para los stacks oci-terraform y multicloud)
#
# Intercambia el JWT OIDC que emite GitHub Actions por un UPST (User Principal
# Session Token) de OCI IAM Identity Domains y configura ~/.oci/config para que
# la CLI de OCI (--auth security_token) y Terraform (auth = "SecurityToken")
# operen con una identidad de vida corta ligada a este job.
#
# Requisitos previos (ver 01-seguridad/02-identidad-federada-oidc.md, sección 3):
#   - Identity Propagation Trust creado en el Identity Domain con emisor
#     https://token.actions.githubusercontent.com y reglas de impersonación
#     que mapean el claim `sub` del repositorio a un usuario de servicio.
#   - Aplicación confidencial del dominio (client id / secret) autorizada para
#     el intercambio de tokens.
#   - El job debe declarar `permissions: id-token: write`.
#
# Variables de entorno esperadas (cargar desde secrets/vars del workflow):
#   OCI_DOMAIN_URL      URL base del Identity Domain (https://idcs-xxxx.identity.oraclecloud.com)
#   OCI_CLIENT_ID       Client ID de la aplicación confidencial
#   OCI_CLIENT_SECRET   Client secret de la aplicación confidencial
#   OCI_TENANCY_OCID    OCID de la tenancy
#   OCI_REGION          Región (p. ej. us-ashburn-1)
#   OCI_OIDC_AUDIENCE   (opcional) audience del token OIDC de GitHub; si está
#                       vacía se usa OCI_DOMAIN_URL. DEBE coincidir con la
#                       audiencia configurada en el Identity Propagation Trust.
#                       El workflow pasa `vars.OCI_OIDC_AUDIENCE || secrets.OCI_DOMAIN_URL`,
#                       exactamente el mismo respaldo que aplica este script.
#
# ADVERTENCIA (AUDITAR/ADAPTAR): los nombres de parámetros del endpoint
# /oauth2/v1/token (requested_token_type, public_key, campo `token` de la
# respuesta) provienen de la documentación de Oracle "JSON Web Token Exchange"
# y de la guía A-Team (jul-2025). Valide contra la documentación vigente de su
# tenancy antes de usar en producción y ajuste si el contrato cambió.
#
# Código de salida: 0 éxito; 1 error de configuración o de intercambio.
# ==============================================================================
set -Eeuo pipefail

: "${OCI_DOMAIN_URL:?Falta OCI_DOMAIN_URL}"
: "${OCI_CLIENT_ID:?Falta OCI_CLIENT_ID}"
: "${OCI_CLIENT_SECRET:?Falta OCI_CLIENT_SECRET}"
: "${OCI_TENANCY_OCID:?Falta OCI_TENANCY_OCID}"
: "${OCI_REGION:?Falta OCI_REGION}"
: "${ACTIONS_ID_TOKEN_REQUEST_URL:?Este script debe ejecutarse en GitHub Actions con id-token: write}"
: "${ACTIONS_ID_TOKEN_REQUEST_TOKEN:?Este script debe ejecutarse en GitHub Actions con id-token: write}"

for herramienta in curl jq openssl; do
  command -v "$herramienta" >/dev/null 2>&1 || { echo "::error::Falta la herramienta '$herramienta'"; exit 1; }
done

OCI_DOMAIN_URL="${OCI_DOMAIN_URL%/}"
# Audience del token OIDC de GitHub: OCI_OIDC_AUDIENCE con respaldo en
# OCI_DOMAIN_URL. Debe coincidir con la audiencia configurada en el Identity
# Propagation Trust; el workflow (ci-oci-terraform.yml) usa el mismo criterio
# (vars.OCI_OIDC_AUDIENCE || secrets.OCI_DOMAIN_URL) — ambos deben coincidir.
OCI_OIDC_AUDIENCE="${OCI_OIDC_AUDIENCE:-$OCI_DOMAIN_URL}"
SESION_DIR="${HOME}/.oci/sessions/DEFAULT"

# 1) Token OIDC de GitHub con la audience configurada.
GH_JWT=$(curl -fsS -H "Authorization: bearer ${ACTIONS_ID_TOKEN_REQUEST_TOKEN}" \
  "${ACTIONS_ID_TOKEN_REQUEST_URL}&audience=${OCI_OIDC_AUDIENCE}" | jq -r .value)
[[ -n "$GH_JWT" && "$GH_JWT" != "null" ]] || { echo "::error::No se obtuvo el JWT OIDC de GitHub"; exit 1; }

# 2) Par de claves RSA efímero: vive solo durante este job; el UPST queda
#    ligado a esta clave pública, por lo que un token robado sin la clave no sirve.
mkdir -p "$SESION_DIR" && chmod 700 "${HOME}/.oci" "$SESION_DIR"
openssl genrsa -out "${SESION_DIR}/oci_api_key.pem" 2048 2>/dev/null
chmod 600 "${SESION_DIR}/oci_api_key.pem"
PUB_DER_B64=$(openssl rsa -in "${SESION_DIR}/oci_api_key.pem" -pubout -outform DER 2>/dev/null | base64 -w0)

# 3) Intercambio JWT → UPST
RESPUESTA=$(curl -fsS -X POST "${OCI_DOMAIN_URL}/oauth2/v1/token" \
  -u "${OCI_CLIENT_ID}:${OCI_CLIENT_SECRET}" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "grant_type=urn:ietf:params:oauth:grant-type:token-exchange" \
  --data-urlencode "requested_token_type=urn:oci:token-type:oci-upst" \
  --data-urlencode "public_key=${PUB_DER_B64}" \
  --data-urlencode "subject_token=${GH_JWT}" \
  --data-urlencode "subject_token_type=jwt") || { echo "::error::El intercambio de token con OCI falló"; exit 1; }
UPST=$(printf '%s' "$RESPUESTA" | jq -r '.token // empty')
[[ -n "$UPST" ]] || { echo "::error::Respuesta sin campo 'token'. Revise la configuración del Identity Propagation Trust"; exit 1; }
echo "::add-mask::${UPST}"
printf '%s' "$UPST" > "${SESION_DIR}/token"
chmod 600 "${SESION_DIR}/token"

# 4) Perfil DEFAULT para CLI y Terraform (auth = SecurityToken)
cat > "${HOME}/.oci/config" <<EOF
[DEFAULT]
region=${OCI_REGION}
tenancy=${OCI_TENANCY_OCID}
key_file=${SESION_DIR}/oci_api_key.pem
security_token_file=${SESION_DIR}/token
EOF
chmod 600 "${HOME}/.oci/config"

# 5) Variables para pasos posteriores del mismo job/workflow
if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "OCI_CLI_AUTH=security_token"
    echo "TF_VAR_oci_auth=SecurityToken"
    echo "OCI_CLI_CONFIG_FILE=${HOME}/.oci/config"
  } >> "$GITHUB_ENV"
fi

# PUNTO DE VERIFICACIÓN: si la identidad quedó bien, este comando responde con
# la tenancy sin pedir credenciales adicionales.
if command -v oci >/dev/null 2>&1; then
  oci iam tenancy get --tenancy-id "$OCI_TENANCY_OCID" --auth security_token --query 'data.name' --raw-output \
    && echo "Federación OCI verificada correctamente." \
    || { echo "::error::La verificación de identidad OCI falló"; exit 1; }
else
  echo "Aviso: la CLI de OCI no está instalada; se omite la verificación (instálela con pip install oci-cli)."
fi
