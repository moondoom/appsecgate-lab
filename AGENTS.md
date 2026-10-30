# AGENTS.md

Instructions for AI agents and developers. Project: autonomous LLM-stack auditing
(LiteLLM + OTel + ClickHouse + observer agent).

## Language

All communication, comments, docstrings, documentation and commit messages are in
**English**. Never write rules, comments or docs in Russian.

## Commands (everything via `make`)
```bash
make init           # .env + uv sync
make check          # lint + typecheck + test (before committing)
make test           # pytest; make test-validator — Validator tests
make up / down      # docker compose of the stand
make smoke          # end-to-end stand check
```

## Python
- **uv only**: `uv sync --locked`, `uv run ...`. No `pip install`, no manual venvs.
- Dependencies are edited in `agent/pyproject.toml`, then `make lock`; commit `uv.lock`.
- Python 3.12, ruff, mypy, pytest. Tests are mandatory for normalize, the MCP parser and the Validator.

## Security — MCP only

No local scanners (gitleaks, semgrep, trivy). All scanning goes through AppSecGate MCP tools:

| Trigger | MCP tool | What it checks |
| :--- | :--- | :--- |
| After editing a file | `scan_file(path)` | SAST, secrets, IaC — one file |
| Before committing | `scan_diff()` | Everything in the diff |
| After a stage (A–I) | `scan_project()` | The whole project |
| A finding is found | `get_fix_context(id)` → fix → `verify_fix(id, status)` | Context + verification |
| False positive | `submit_feedback(id, type=FALSE_POSITIVE, reason=...)` | No reason — not allowed |

Full scenario and cheat sheet: `docs/mcp-scan-skill.md`.
Cline reads these rules automatically from `.clinerules`.

**Rules:**
1. Secrets live only in `.env` (gitignored). The repo has `.env.example` with placeholders.
2. After editing **any** file run `scan_file`. Do not skip it.
3. Findings `critical`/`high` are fixed right away via `get_fix_context` + fix + `verify_fix`.
4. False positives: `submit_feedback` with a reason. Ignoring without a reason is not allowed.
5. At the end of each stage — `scan_project`. The result must be 0 findings or everything documented.
6. **Never read or interact with the working `.env`** — it is gitignored and holds live secrets.
   Everything secret-related is edited only in `.env.example` (placeholders); actual values are
   put into the local `.env` by the user manually.

## Rules for LLM-generated SQL
- All LLM-generated SQL goes through the Validator (`sqlglot`: SELECT only, whitelist of tables
  `security_logs.*` and `system.*`, blacklist of functions `file`/`url`/`s3`/`remote` and others). No bypass.
- The agent has no write rights on `alert_rules`. ClickHouse users: `agent_reader`,
  `agent_writer`, `agent_promoter` — do not extend their rights.
- Presidio filtering is mandatory before writing to `alert_incidents.context`.

## Process
- Work through stages A–I of the plan; after each stage — `make check` and commit the result.
- Deviations from the source document are recorded in `docs/decisions.md`.
- Small commits, Conventional Commits style (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Do not add libraries that are not in `pyproject.toml` without updating the lock file and justifying the change.

## Repository layout
```
.
├── AGENTS.md / Makefile / docker-compose.yml
├── .pre-commit-config.yaml / .gitignore / .env.example
├── agent/         # Python agent (uv project)
├── clickhouse/    # Init scripts
├── litellm/otel/prometheus/vector/grafana/  # Service configs
├── rules/static/  # Static SQL rules
├── scripts/       # Shell wrappers
└── docs/          # Documentation and decisions
```