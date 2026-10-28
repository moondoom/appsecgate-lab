# AGENTS.md

Инструкции для ИИ-агентов и разработчиков. Проект: автономный аудит LLM-стенда
(LiteLLM + OTel + ClickHouse + агент-наблюдатель).

## Команды (всё через `make`)
```bash
make init           # .env + uv sync
make check          # lint + typecheck + test (перед коммитом)
make test           # pytest; make test-validator — тесты Validator
make up / down      # docker compose стенда
make smoke          # сквозная проверка стенда
```

## Python
- **Только uv**: `uv sync --locked`, `uv run ...`. Никаких `pip install` и ручных venv.
- Зависимости правим в `agent/pyproject.toml`, затем `make lock`; `uv.lock` коммитим.
- Python 3.12, ruff, mypy, pytest. Тесты обязательны для normalize, MCP-парсера и Validator.

## Безопасность — только MCP

Никаких локальных сканеров (gitleaks, semgrep, trivy). Всё сканирование — через инструменты AppSecGate MCP:

| Триггер | Инструмент MCP | Что проверяет |
| :--- | :--- | :--- |
| После правки файла | `scan_file(path)` | SAST, секреты, IaC — один файл |
| Перед коммитом | `scan_diff()` | Все изменения в диффе |
| После этапа (A–I) | `scan_project()` | Весь проект целиком |
| Нашлась находка | `get_fix_context(id)` → правишь → `verify_fix(id, status)` | Контекст + верификация |
| Ложное срабатывание | `submit_feedback(id, type=FALSE_POSITIVE, reason=...)` | Без причины — нельзя |

Полный сценарий и шпаргалка: `docs/mcp-scan-skill.md`.
Cline читает эти правила автоматически из `.clinerules`.

**Правила:**
1. Секреты только в `.env` (в `.gitignore`). В репозитории — `.env.example` с плейсхолдерами.
2. После правки **любого** файла вызывать `scan_file`. Перед коммитом — `scan_diff`.
3. Находки `critical`/`high` исправлять сразу через `get_fix_context` + правка + `verify_fix`.
4. Ложные срабатывания: `submit_feedback` с причиной. Игнорировать без причины — нельзя.
5. В конце каждого этапа — `scan_project`. Результат должен быть 0 findings или все задокументированы.

## Правила для SQL от LLM
- Весь SQL, сгенерированный LLM, проходит Validator (`sqlglot`: только SELECT, whitelist таблиц `security_logs.*` и `system.*`, blacklist функций `file`/`url`/`s3`/`remote` и др.). Обхода нет.
- Агент не имеет прав записи в `alert_rules`. Пользователи ClickHouse: `agent_reader`, `agent_writer`, `agent_promoter` — права не расширять.
- Presidio-фильтр обязателен перед записью `alert_incidents.context`.

## Процесс
- Работать по этапам A–I из плана; после этапа — `make check` и фиксация результата.
- Расхождения с исходным документом записывать в `docs/decisions.md`.
- Коммиты небольшие, сообщения в стиле Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`, `test:`).
- Не добавлять библиотеки, которых нет в `pyproject.toml`, без обновления lock-файла и обоснования.

## Структура репозитория
```
.
├── AGENTS.md / Makefile / docker-compose.yml
├── .pre-commit-config.yaml / .gitignore / .env.example
├── agent/         # Python-агент (uv-проект)
├── clickhouse/    # Init-скрипты
├── litellm/otel/prometheus/vector/grafana/  # Конфиги сервисов
├── rules/static/  # Статические SQL-правила
├── scripts/       # shell-обёртки
└── docs/          # Документация и решения
```