# AppSecGate Lab

> ## ⚠️ TEST LABORATORY — USE AT YOUR OWN RISK!!!
>
> This repository is a **test laboratory / playground** for the
> **[moondoom/appsecgate-mcp](https://github.com/moondoom/appsecgate-mcp)** project.
> It exists to practice techniques, run experiments and validate hypotheses **in a
> sandbox** — none of it is a production system.
>
> **Use it at your own risk!** No warranty, express or implied. Do not deploy this
> stack to production, do not feed it real sensitive data, and do not rely on any
> security guarantees coming from this lab.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](agent/pyproject.toml)
[![Package manager](https://img.shields.io/badge/package%20manager-uv-4F46E5)](https://docs.astral.sh/uv/)
[![Docker Compose](https://img.shields.io/badge/docker%20compose-13%20services-2496ED)](docker-compose.yml)
[![Part of](https://img.shields.io/badge/part%20of-appsecgate--mcp-4CAF50)](https://github.com/moondoom/appsecgate-mcp)
[![Status: TEST LAB](https://img.shields.io/badge/status-TEST%20LAB-important)](README.md)
[![GitHub stars](https://img.shields.io/github/stars/moondoom/appsecgate-lab)](https://github.com/moondoom/appsecgate-lab)
[![GitHub last commit](https://img.shields.io/github/last-commit/moondoom/appsecgate-lab)](https://github.com/moondoom/appsecgate-lab)

---

## Product description

**One-liner:**

> Sandboxed LLM-stack lab (LiteLLM + OpenTelemetry + ClickHouse + observer agent)
> built as a test bed for the AppSecGate MCP project.

**Short:**

> A lab environment for practicing autonomous LLM-stack auditing: LiteLLM traffic is
> captured via OpenTelemetry into ClickHouse, and a Python observer agent normalizes
> events, correlates anomalies and drafts SQL detection rules.

**Medium:**

> Spin up a 13-service `docker compose` stack (LiteLLM, OTel Collector, Jaeger,
> ClickHouse, Prometheus, Grafana, Presidio, Vector) plus a Python agent that watches
> the event stream, detects anomalies and proposes rules for review. Everything here is
> an experiment — use at your own risk!

**Long:**

> AppSecGate Lab is an autonomous-audit sandbox for LLM stacks. LiteLLM acts as the
> traffic source (an LLM-model proxy wrapped in OpenTelemetry); traces, metrics and
> spend logs land in ClickHouse. A Python agent runs a closed loop —
> **normalize → correlate → propose** — turning raw events into `security_logs` views,
> running static SQL correlation rules against them, and producing rule/asset proposals
> for a human (or the parent MCP project) to review. Prometheus/Grafana expose stand
> metrics; Presidio scrubs PII before incident context is persisted.
>
> The whole point is **practice**: this is a laboratory for the
> [moondoom/appsecgate-mcp](https://github.com/moondoom/appsecgate-mcp) project, not a
> product. Expect rough edges, incomplete flows and deliberate experiments.

**For GitHub About / repo description:**

```
Test lab for AppSecGate MCP: LLM stack (LiteLLM + OTel + ClickHouse + observer agent)
for practicing autonomous auditing. Not production — use at your own risk!
```

**Suggested topics:** `appsec`, `llm-security`, `litellm`, `opentelemetry`, `clickhouse`,
`grafana`, `prometheus`, `presidio`, `lab`, `testbed`, `mcp`, `autonomous-agent`

---

## What it is

A 13-service `docker compose` stack plus a Python agent (`agent/`):

- **LiteLLM** — LLM-model proxy, the traffic source (wrapped in OpenTelemetry).
- **Postgres** — LiteLLM's internal database: virtual keys, teams, budgets and Admin UI CRUD.
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
# fill passwords in .env (rand -hex 32 etc.) — incl. LITELLM_DB_PASS and LITELLM_UI_PASSWORD
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

> The `postgres` service (LiteLLM internal DB — virtual keys, teams, budgets,
> Admin UI CRUD) stays inside `llm-net` and is not exposed to the host.

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
└── docker-compose.yml      # 13 services
```

## Dashboards (Grafana)

Two provisioned dashboards live in the **AppSecGate** folder
(`grafana/provisioning/dashboards/`, auto-reloaded every 30 s):

| Dashboard | What it shows |
| :--- | :--- |
| **Agent Activity Control** | LLM requests (statuses, cost, tokens, TTFT p95), tools, guardrails, incidents + small badges of agent Prometheus metrics |
| **Raw Views Explorer** | Full rows of `security_logs.*` tables: requests, tool calls, guardrails, incidents, assets and proposals — with filters |

JSON is generated by `scripts/gen_dashboards.py` (stdlib only, only `SELECT`):

```bash
make dashboards      # regenerate JSON
docker compose restart grafana   # when adding the provider for the first time
```

Grafana → http://localhost:3000, folder **AppSecGate**.

## Screenshots

| Dashboard | Screenshot |
| :--- | :--- |
| **Agent Activity Control** | [`docs/img/agent-activity-control.png`](docs/img/agent-activity-control.png) |
| **Raw Views Explorer** | [`docs/img/raw-views-explorer.png`](docs/img/raw-views-explorer.png) |

## LiteLLM Admin UI

The proxy ships a built-in admin UI at **http://localhost:4000/ui** — create
virtual keys, teams, budgets and manage models without touching config.yaml.

Login uses `LITELLM_UI_USERNAME` / `LITELLM_UI_PASSWORD` from `.env`; if
`LITELLM_UI_PASSWORD` is left empty, the master key (`LITELLM_API_KEY`) is
accepted as the password. API reference (Swagger): http://localhost:4000/.

For the UI's CRUD operations LiteLLM needs its internal SQL database — the
`postgres` service (13th in the stack, see above).

## Security: MCP only

No local scanners. All scanning goes through AppSecGate MCP tools
(`scan_file` after editing a file, `scan_diff` before committing, `scan_project`
after a stage). Full scenario: `docs/mcp-scan-skill.md`. Cline picks up the
rules automatically from `.clinerules`.

## Related

- **[moondoom/appsecgate-mcp](https://github.com/moondoom/appsecgate-mcp)** — the parent
  MCP server project this lab is built for and practices against.
- `docs/mcp-scan-skill.md` — the AppSecGate MCP scanning skill used in this lab.

## Status

The stack is wired end-to-end in the sandbox: LiteLLM traffic → ClickHouse
`spend_logs` → derived `security_logs` views → observer/correlator/rule-engine
loop → proposals, with Grafana dashboards on top. Everything is exercised on
test data only. Tracked decisions and deviations: `docs/decisions.md`.

## License

[MIT](LICENSE) © [moondoom](https://github.com/moondoom/appsecgate-mcp). See `LICENSE`.

