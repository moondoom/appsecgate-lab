SHELL := /bin/bash
.DEFAULT_GOAL := help

COMPOSE  ?= docker compose
AGENT_DIR := agent
UV       := uv --project $(AGENT_DIR)

.PHONY: help init sync lock lint fmt typecheck test test-validator check \
        up up-gpu down clean ps logs config \
        ch-init ch-shell \
        load-rules observe correlate propose promote \
        smoke

help: ## Показать эту справку
	@awk 'BEGIN {FS = ":.*##"; printf "\nЦели:\n"} /^[a-zA-Z0-9_-]+:.*##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

init: .env sync ## .env + uv sync

.env:
	@if [ ! -f .env ]; then cp .env.example .env; echo "  -> .env created from .env.example -- fill passwords"; fi

sync: ## uv sync --locked
	$(UV) sync --locked

lock: ## uv lock
	$(UV) lock

lint: ## ruff check + format
	$(UV) run ruff check src
	$(UV) run ruff format --check src

fmt: ## ruff format + fix
	$(UV) run ruff format src
	$(UV) run ruff check --fix src

typecheck: ## mypy
	$(UV) run mypy src

test: ## pytest
	$(UV) run pytest -q --tb=short

test-validator: ## Only Validator tests
	$(UV) run pytest -q --tb=short -k validator

check: lint typecheck test ## Full check (lint + typecheck + test)

up: ## Start stack
	$(COMPOSE) up -d --build

up-gpu: ## Start stack with GPU profile
	$(COMPOSE) --profile gpu up -d --build

down: ## Stop stack
	$(COMPOSE) down

clean: ## Remove all volumes (needs CONFIRM=1)
	@if [ "$(CONFIRM)" = "1" ]; then \
		$(COMPOSE) down -v; \
		echo "  -> volumes removed"; \
	else \
		echo "  -> set CONFIRM=1 to actually remove volumes"; \
	fi

ps: ## Service status
	$(COMPOSE) ps

logs: ## Logs (SVC=<name>)
	$(COMPOSE) logs --tail=50 $(SVC)

config: ## Validate docker-compose.yml
	$(COMPOSE) config -q
	@echo "  -> config valid"

ch-init: ## Apply init scripts
	@for f in clickhouse/init/*.sql; do \
		echo "-> $$f"; \
		cat $$f | $(COMPOSE) exec -T clickhouse clickhouse-client --multiquery; \
	done

ch-shell: ## Connect to ClickHouse
	$(COMPOSE) exec clickhouse clickhouse-client

load-rules: ## Load static rules
	$(UV) run python -m agent.cli load-rules rules/static

observe: ## Run Observer once
	$(UV) run python -m agent.cli observe

correlate: ## Run Correlator once
	$(UV) run python -m agent.cli correlate

propose: ## Run Rule-Engine once
	$(UV) run python -m agent.cli propose

promote: ## Promote rule (ID=<uuid>)
	$(UV) run python -m agent.cli promote $(ID)

smoke: ## End-to-end smoke test
	bash scripts/smoke.sh
