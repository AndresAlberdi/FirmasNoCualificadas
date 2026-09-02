SHELL := /bin/bash
ENV ?= dev
PY  := services/.venv/bin/python
TF_DIR := infra/terraform/envs/$(ENV)
# Jurisdicción cuyo perfil se exporta a Terraform (ver ADR-0008).
JURISDICCION ?= PY

# Gestión de paquetes (ver `docs/adr/0009-contrato-de-compatibilidad-con-tenants.md`
# y CLAUDE.md): `uv` para Python con `uv.lock` versionado, y `pnpm` vía Corepack
# con `ignore-scripts=true` para todo lo que sea Node. No se usa `npm install`.
UV   := uv
PNPM := COREPACK_ENABLE_DOWNLOAD_PROMPT=0 corepack pnpm

.DEFAULT_GOAL := help

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- Backend ----
.PHONY: setup
setup: ## Crea el entorno virtual e instala dependencias de backend y dashboard
	cd services && $(UV) venv --python 3.12
	cd services && $(UV) sync --extra dev
	cd dashboard && $(PNPM) install --frozen-lockfile

.PHONY: test
test: lint ## Ejecuta la batería de pruebas del backend
	cd services && .venv/bin/pytest -q

.PHONY: lint
lint: ## Análisis estático (ruff + mypy)
	# Se ejecuta DENTRO de `services/`: es donde vive el `pyproject.toml` con la
	# configuración de ambas herramientas. Corriéndolo desde la raíz, mypy no
	# carga el plugin de Pydantic y reporta errores que la configuración real no
	# tiene — un falso positivo que además oculta los verdaderos.
	cd services && .venv/bin/ruff check src tests
	cd services && .venv/bin/ruff format --check src tests
	cd services && .venv/bin/mypy src

.PHONY: run-api
run-api: ## Levanta la API B2B en modo desarrollo
	services/.venv/bin/uvicorn pscnc.orchestrator.app:app --reload --port 8080 --app-dir services/src

.PHONY: docker-build
docker-build: ## Construye la imagen del servicio de firma
	docker build -t pscnc/signer:local services

# -------------------------------------------------------------- Dashboard ----
.PHONY: run-dashboard
run-dashboard: ## Levanta el dashboard B2B
	cd dashboard && $(PNPM) run dev

.PHONY: build-dashboard
build-dashboard: ## Compila el dashboard para producción
	cd dashboard && $(PNPM) run build

.PHONY: lint-dashboard
lint-dashboard: ## ESLint y verificación de tipos del dashboard
	cd dashboard && $(PNPM) run lint
	cd dashboard && $(PNPM) run typecheck

# -------------------------------------------------------------- Terraform ----
.PHONY: tf-init tf-plan tf-apply tf-fmt tf-validate tf-test tf-jurisdiccion
tf-init: ## terraform init del entorno ENV (por defecto dev)
	terraform -chdir=$(TF_DIR) init

tf-plan: ## terraform plan del entorno ENV
	terraform -chdir=$(TF_DIR) plan -out=tfplan

tf-apply: ## terraform apply del plan generado
	terraform -chdir=$(TF_DIR) apply tfplan

tf-fmt: ## Normaliza el formato HCL
	terraform fmt -recursive infra/terraform

tf-validate: ## Valida la sintaxis de todos los entornos
	terraform -chdir=$(TF_DIR) validate

.PHONY: tf-test
tf-test: ## Pruebas de la infraestructura (compuerta de conservación, sin credenciales)
	terraform -chdir=infra/terraform/modules/retention-gate init -backend=false -input=false
	terraform -chdir=infra/terraform/modules/retention-gate test

.PHONY: tf-jurisdiccion
tf-jurisdiccion: ## Regenera jurisdiccion.auto.tfvars del entorno ENV desde el perfil
	$(PY) scripts/exportar-jurisdiccion.py $(JURISDICCION) $(TF_DIR)

# ------------------------------------------------------------- Seguridad -----
.PHONY: security
security: ## Escaneos de seguridad locales
	cd services && .venv/bin/bandit -q -c pyproject.toml -r src
	@command -v checkov >/dev/null && checkov -d infra/terraform --quiet || echo "checkov no instalado, omitido"
