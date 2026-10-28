# AppSecGate Lab

Лабораторный стенд для отработки методов автономного аудита LLM-стенда:
поведение модель-прокси (LiteLLM) фиксируется через OpenTelemetry и ClickHouse,
а агент-наблюдатель анализирует поток событий и выявляет аномалии.

> Это **тестовый полигон / лаборатория**: здесь отрабатываются техники,
> пишутся эксперименты и проверяются гипотезы. Ничего из этого репозитория
> не является боевой системой.

## Что это

Композ из 12 сервисов, поднимаемых `docker compose`, плюс Python-агент (`agent/`):

- **LiteLLM** — прокси для LLM-моделей, является источником трафика (обёрнуто в OTel).
- **OpenTelemetry Collector** — приём трейсов/метрик, экспорт в Jaeger и ClickHouse.
- **Jaeger** — визуализация трейсов для отладки.
- **ClickHouse** — хранилище логов, трейсов и результатов корреляции.
- **Агент-наблюдатель** — нормализация событий, корреляция, правило-движок.
- **Prometheus + Grafana + node-exporter + cAdvisor + GPU-exporter** — метрики стенда.
- **Presidio** — фильтрация PII перед записью контекста инцидентов.
- **Vector** *(профиль `audit`)* — разбор auditd-логов.

## Быстрый старт

```bash
make init        # создать .env из .env.example + uv sync
# заполнить пароли в .env (rand -hex 32 и т.п.)
make up          # docker compose up -d --build
make config      # проверить конфиг compose
make ch-init     # применить clickhouse/init/*.sql (если не применились автоматически)
make smoke       # сквозная проверка стенда
make check       # lint + typecheck + test
```

Порты по умолчанию:

| Сервис | Порт   |
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

## Команды

| Команда | Что делает |
| :--- | :--- |
| `make up` / `down` / `ps` / `logs` | жизнь compose |
| `make ch-init` / `ch-shell` | ClickHouse: init-скрипты, клиент |
| `make load-rules` | загрузить статические правила в `alert_rules` |
| `make observe` / `correlate` / `propose` | разовый запуск модулей агента |
| `make smoke` | сквозная проверка стенда |
| `make check` | ruff + mypy + pytest перед коммитом |

## Структура

```
.
├── agent/                  # Python-агент (uv, Python 3.12)
│   ├── src/agent/          # cli, config, db, metrics, observer/normalize
│   └── tests/              # pytest (нормализация и пр.)
├── clickhouse/init/        # 7 SQL-скриптов: БД, пользователи, таблицы, функции, правила
├── litellm/ otel/ prometheus/ vector/ grafana/   # конфиги сервисов
├── rules/static/           # 5 статических SQL-правил корреляции
├── docs/                   # решения (decisions.md), MCP-скилл
└── docker-compose.yml      # 12 сервисов
```

## Безопасность: только MCP

Никаких локальных сканеров. Всё сканирование — через инструменты AppSecGate MCP
(`scan_file` после правки файла, `scan_diff` перед коммитом, `scan_project` после этапа).
Полный сценарий: `docs/mcp-scan-skill.md`. Для Cline правила подхватываются из `.clinerules`.

## Статус

Этап 0 (scaffolding) завершён: структура, compose, конфиги, деплой-скрипты,
скелет агента с тестами. Далее — этап A: проверка потока трейсов LiteLLM в Jaeger/ClickHouse.

---

## Описание проекта (для метаданных)

**Короткое (одна строка):**
> Лабораторный стенд для тестирования LLM-стека: LiteLLM + OpenTelemetry + ClickHouse + агент-наблюдатель.

**Среднее (несколько строк):**
> Тестовый полигон для исследования поведения LLM-стенда. Поднимает композ
> (LiteLLM, OTel, ClickHouse, Grafana) и Python-агента, который наблюдает за
> потоком событий. Всё — эксперименты и отработка техник, не боевой контур.

**Для GitHub About / описание репозитория:**
```
LLM-стенд для тестов и экспериментов: LiteLLM + OTel + ClickHouse + агент-наблюдатель.
Лаборатория, не production. Поток событий → ClickHouse → корреляция → предложения по правилам.
```