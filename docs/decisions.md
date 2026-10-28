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
| 10 | .clinerules вместо pre-commit hooks для безопасности | Cline читает .clinerules автоматически |

