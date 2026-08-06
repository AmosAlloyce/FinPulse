.PHONY: help install test lint format local-demo up down producer logs dbt-test smoke clean

help: ## Show available commands
	@awk 'BEGIN {FS = ":.*##"; printf "\nFinPulse commands:\n\n"} /^[a-zA-Z_-]+:.*?##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Create a virtual environment and install development dependencies
	python3 -m venv .venv
	.venv/bin/pip install -e '.[dev,dashboard]'

test: ## Run fast unit tests with coverage
	.venv/bin/pytest --cov=finpulse --cov-report=term-missing

lint: ## Run Ruff checks
	.venv/bin/ruff check src tests airflow/dags

format: ## Format source and tests
	.venv/bin/ruff format src tests airflow/dags
	.venv/bin/ruff check --fix src tests airflow/dags

local-demo: ## Run the zero-infrastructure local pipeline demo
	.venv/bin/finpulse local-demo --events 10000 --output artifacts/local-demo

up: ## Start the core streaming platform and dashboard
	docker compose up --build -d postgres redpanda redpanda-console minio minio-init producer stream-processor api dashboard

observe: ## Start Prometheus and Grafana
	docker compose --profile observability up -d prometheus grafana

orchestrate: ## Start Airflow scheduler and webserver
	docker compose --profile orchestration up --build -d airflow-init airflow-scheduler airflow-webserver

down: ## Stop the platform
	docker compose --profile observability --profile orchestration down

logs: ## Follow application logs
	docker compose logs -f producer stream-processor api dashboard

dbt-test: ## Build and test warehouse models
	docker compose --profile orchestration run --rm dbt build --profiles-dir /usr/app/dbt

smoke: ## Verify health endpoints and platform dependencies
	./scripts/smoke_test.sh

clean: ## Remove local generated artifacts (containers are untouched)
	rm -rf artifacts .coverage htmlcov .pytest_cache .ruff_cache
