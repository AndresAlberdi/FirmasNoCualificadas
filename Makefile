SHELL := /bin/bash
ENV ?= dev
PY  := services/.venv/bin/python
PIP := services/.venv/bin/pip
TF_DIR := infra/terraform/envs/$(ENV)

.DEFAULT_GOAL := help

.PHONY: help
help: ## Muestra esta ayuda
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ---------------------------------------------------------------- Backend ----
.PHONY: setup
setup: ## Crea el entorno virtual e instala dependencias de backend y dashboard
	python3 -m venv services/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -e "services[dev]"
	cd dashboard && npm install

.PHONY: test
test: lint ## Ejecuta la batería de pruebas del backend
	cd services && .venv/bin/pytest -q

.PHONY: lint
lint: ## Análisis estático (ruff + mypy)
	services/.venv/bin/ruff check services/src services/tests
	services/.venv/bin/ruff format --check services/src services/tests
	services/.venv/bin/mypy services/src

.PHONY: run-api
run-api: ## Levanta la API B2B en modo desarrollo
	services/.venv/bin/uvicorn pscnc.orchestrator.app:app --reload --port 8080 --app-dir services/src

.PHONY: docker-build
docker-build: ## Construye la imagen del servicio de firma
	docker build -t pscnc/signer:local services

# -------------------------------------------------------------- Dashboard ----
.PHONY: run-dashboard
run-dashboard: ## Levanta el dashboard B2B
	cd dashboard && npm run dev

.PHONY: build-dashboard
build-dashboard: ## Compila el dashboard para producción
	cd dashboard && npm run build

# -------------------------------------------------------------- Terraform ----
.PHONY: tf-init tf-plan tf-apply tf-fmt tf-validate
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

# ------------------------------------------------------------- Seguridad -----
.PHONY: security
security: ## Escaneos de seguridad locales
	services/.venv/bin/bandit -q -r services/src
	@command -v checkov >/dev/null && checkov -d infra/terraform --quiet || echo "checkov no instalado, omitido"
