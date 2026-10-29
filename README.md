# AppSecGate Lab

A lab environment for practicing autonomous LLM-stack auditing:
model-proxy behavior (LiteLLM) is captured via OpenTelemetry into ClickHouse,
and an observer agent analyzes the event stream and surfaces anomalies.

> This is a **test playground / laboratory**: techniques get practiced here,
> experiments are written, hypotheses are validated. None of this repository
> is a production system.

## What it is

A 12-service `docker compose` stack plus a Python agent (`agent/`):

- **LiteLLM** — LLM-model proxy, the traffic source (wrapped in OpenTelemetry).
- **OpenTelemetry Collector** — receives traces/metrics, exports to Jaeger and ClickHouse.
- **Jaeger** — trace visualization for debugging.
- **ClickHouse** — storage for logs, traces and correlation results.
- **Observer agent** — event normalization, correlation, rule engine.
- **Prometheus + Grafana + node-exporter + cAdvisor + GPU-exporter** — stand metrics.
- **Presidio** — PII filtering before incident context is persisted.
- **Vector** *(profile `audit`)* — auditd log parsing.

## Quick start

```bash
make init        # create .env from .env.example + uv sync
# fill passwords in .env (rand -hex 32 etc.)
make up          # docker compose up -d --build
make config      # validate compose config
make ch-init     # apply clickhouse/init/*.sql (if not auto-applied)
make smoke       # end-to-end stack check
make check       # lint + typecheck + test
```

Default ports:

| Service | Port |
| :--- | :--- |
| LiteLLM | `4000` |
| Jaeger UI | `16686` |
| OTel Collector | `4317`/`4318` |
| ClickHouse HTTP | `8123` |
| Prometheus | `9090` |
| Grafana | `3000` |
| Presidio | `5002` |
| node-exporter / cAdvisor / GPU | `9100` / `8080` / `9835` |
| agent-observer metrics | `9101` |

## Commands

| Command | What it does |
| :--- | :--- |
| `make up` / `down` / `ps` / `logs` | compose lifecycle |
| `make ch-init` / `ch-shell` | ClickHouse: init scripts, client |
| `make load-rules` | load static rules into `alert_rules` |
| `make observe` / `correlate` / `propose` | single-run agent modules |
| `make promote ID=<uuid>` | promote approved proposal into `alert_rules` |
| `make serve` | scheduled agent loop (observer/correlator/rule-engine) |
| `make dashboards` | regenerate Grafana dashboard JSONs (`scripts/gen_dashboards.py`) |
| `make smoke` | end-to-end stack check |
| `make check` | ruff + mypy + pytest before commit |

## Layout

```
.
├── agent/                  # Python agent (uv, Python 3.12)
│   ├── src/agent/          # cli, config, db, metrics, observer/normalize
│   └── tests/              # pytest (normalization and more)
├── clickhouse/init/        # 8 SQL scripts: DBs, users, tables, functions, rules, derived views
├── litellm/ otel/ prometheus/ vector/ grafana/   # service configs
├── rules/static/           # 10 static SQL correlation rules
├── docs/                   # decisions.md, MCP skill
└── docker-compose.yml      # 12 services
```

## Dashboards (Grafana)

Two provisioned dashboards live in the **AppSecGate** folder
(`grafana/provisioning/dashboards/`, auto-reloaded every 30 s):

| Dashboard | What it shows |
| :--- | :--- |
| **Агент: контроль действий** | LLM-запросы (статусы, стоимость, токены, TTFT p95), инструменты, гардрейлы, инциденты + маленькие бейджи Prometheus-метрик агента |
| **Сырые данные из view** | Полные строки таблиц `security_logs.*`: запросы, tool calls, guardrails, инциденты, активы и предложения — с фильтрами |

JSON генерируются `scripts/gen_dashboards.py` (только stdlib, только `SELECT`):

```bash
make dashboards      # перегенерировать JSON
docker compose restart grafana   # при первом добавлении провайдера
```

Grafana → http://localhost:3000, папка **AppSecGate**.

## Security: MCP only

No local scanners. All scanning goes through AppSecGate MCP tools
(`scan_file` after editing a file, `scan_diff` before committing, `scan_project`
after a stage). Full scenario: `docs/mcp-scan-skill.md`. Cline picks up the
rules automatically from `.clinerules`.

## Status

Stage 0 (scaffolding) is done: layout, compose, configs, deployment scripts,
agent skeleton with tests. Next — stage A: verifying the LiteLLM trace flow in
Jaeger/ClickHouse.

---

## Project description (for metadata)

**Short (one line):**
> Lab environment for testing an LLM stack: LiteLLM + OpenTelemetry + ClickHouse + observer agent.

**Medium (a few lines):**
> A test playground for studying LLM-stack behavior. Spins up a compose stack
> (LiteLLM, OTel, ClickHouse, Grafana) and a Python agent that watches the
> event stream. Everything here is experiments and technique practice, not a
> production system.

**For GitHub About / repo description:**
```
LLM stack for tests and experiments: LiteLLM + OTel + ClickHouse + observer agent.
A lab, not production. Event stream → ClickHouse → correlation → rule proposals.
```