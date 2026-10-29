# Архитектурные решения

## Отклонения от source.md

| № | Решение | Причина |
| :--- | :--- | :--- |
| 1 | Python-проект через uv, а не requirements.txt | Единый lock-файл, кэширование слоёв в Docker |
| 2 | OTel Collector пишет в otel_traces, Observer разбирает | Exporter clickhouse не умеет писать в произвольные таблицы |
| 3 | ReplacingMergeTree с updated_at, а не с наблюдением | Счётчики агрегируются перед вставкой |
| 4 | rule_proposals — ReplacingMergeTree | Обновление статуса без дублирования |
| 5 | SQL-правила переписаны с LEFT JOIN вместо коррелированного NOT EXISTS | ClickHouse не оптимизирует коррелированные подзапросы |
| 6 | Нет Kestra в первой версии | APScheduler достаточен для MVP |
| 7 | Нет эмбеддингов в agent_memory на MVP | Требует выбора модели, отложено на Этап H |
| 8 | .gitleaks.toml — allowlist для .env.example и тестов | Без него pre-commit блокирует коммит конфигов |
| 9 | Только MCP-сканирование, никаких локальных сканеров | Пользователь: «только MCP, только хардкор» |
| 11 | ClickHouse URL: формат `http://user:pass@host:8123/db` (не `clickhouse://`) | Rust bridge (с v1.109.0) парсит HTTP-URL напрямую |
| 12 | `/metrics` вынесен на порт 4001 через `PROMETHEUS_METRICS_PORT` | С v1.101.0 /metrics обслуживается отдельным процессом; на основном порту — 404 без callback prometheus |
| 13 | otel-collector — явный `command: ["--config", "/etc/otelcol/config.yaml"]` | Образ `otel/opentelemetry-collector-contrib` по умолчанию читает `/etc/otelcol-contrib/config.yaml` (дефолтный), наш конфиг не применялся |
| 14 | `make ch-ensure` вызывает `ensure_schema()` вручную через python | Rust bridge не вызывает `ensure_schema` при инициализации; без таблицы `spend_logs` insert падает с HTTP 404 |
| 15 | Для proxyapi/aitunnel провайдер задаётся префиксом `openai/` в `model` | По докам LiteLLM для OpenAI-compatible достаточно `openai/<model>` + `api_base`; `custom_llm_provider` не требуется |

