# Таблица `litellm.spend_logs` — справочный отчёт

> Собран 29.10.2026 на живых данных стенда (LiteLLM `main-latest`, API v1.109.0).

## 1. Роль в проекте

`spend_logs` — таблица расходов/телеметрии LiteLLM-прокси. Это **единственный реальный
источник наблюдаемости на стенде** (решение №18 в `docs/decisions.md`): OTel-пайплайн
трасс не реализован, а `spend_logs` пишет сам LiteLLM при каждом запросе.
Observer-агент читает её и превращает наблюдения в предложения активов
(`asset_proposals`).

LiteLLM на стенде: образ `ghcr.io/berriai/litellm:main-latest`, версия API
`litellm_api_version = 1.109.0` (видно в metadata).

## 2. Кто создаёт и поддерживает схему

- Схему создаёт **сам LiteLLM** через `ClickHouseSpendStorage.ensure_schema()`
  из `litellm.rust_bridge.clickhouse` — вручную, потому что rust-bridge **не вызывает**
  `ensure_schema` при инициализации (решение №14).
- В проекте это обёрнуто в `make ch-ensure`
  (`docker compose exec litellm python3 -c "..."`); `make up-full` = `up` + `ch-init` + `ch-ensure`.
- Подключение: `CLICKHOUSE_URL: http://default:${CLICKHOUSE_DEFAULT_PASS}@clickhouse:8123`
  + `CLICKHOUSE_DATABASE: litellm` (docker-compose, решение №23: читаются только эти
  две переменные, другие варианты конфигурации нерабочие).
- Прогресс схемы хранится в таблице `litellm._litellm_spend_migrations` (MergeTree).
  Сейчас применены 5 миграций:
  v6 «spend logs», v7 «spend logs ttl», v14 «spend unknown cost»,
  v15 «spend gateway call id», v16 «spend provider request id».

## 3. Физическая структура

```sql
ENGINE = ReplacingMergeTree(end_time)   -- end_time как версия для дедупликации
PARTITION BY toYYYYMM(start_time)       -- партиция = месяц
ORDER BY (team_id, start_time, request_id)  -- первичный ключ
TTL toDateTime(start_time) + toIntervalDay(14)   -- данные живут 14 дней
SETTINGS materialize_ttl_recalculate_only = 1, index_granularity = 8192
```

- **5 bloom-фильтров** (GRANULARITY 1): `idx_response_id`, `idx_trace_id`,
  `idx_litellm_call_id`, `idx_request_id`, `idx_provider_request_id` — для
  точечного поиска по UUID.
- Текущее состояние: **267 строк**, 5 активных партов, ~10.9 МБ (сжато), 25 marks.
- Ограничение: данные удаляются через 14 дней от `start_time` — история не хранится дольше.

## 4. Колонки (37 шт.)

### Идентификаторы

| Колонка | Тип | Описание |
|---|---|---|
| `request_id` | `String` | Уникальный ID запроса через прокси (UUID или W3C-trace-id-подобный) |
| `response_id` | `String` | ID ответа |
| `provider_request_id` | `String DEFAULT ''` | ID на стороне провайдера (из заголовка `request-id`) |
| `litellm_call_id` | `String DEFAULT ''` | Внутренний call ID LiteLLM |

### Субъекты и маршрутизация

| Колонка | Тип | Описание |
|---|---|---|
| `api_key` | `String` | Хеш виртуального ключа (`litellm_proxy_master_key` у мастер-ключа) |
| `key_alias` | `String` | Алиас ключа |
| `team_id` / `team_alias` | `LowCardinality(String)` / `String` | Команда |
| `organization_id` | `String` | Организация |
| `user` | `String` | Кто ходит через прокси (в данных: `default_user_id`) |
| `end_user` | `String` | Конечный пользователь |
| `call_type` | `LowCardinality(String)` | Тип вызова: `acompletion`, `completion`, ... |

### Модель и провайдер

| Колонка | Тип | Описание |
|---|---|---|
| `model` | `LowCardinality(String)` | `openai/deepseek/deepseek-v4-flash-0731` |
| `model_group` | `LowCardinality(String)` | `p/deepseek-v4-flash` |
| `model_id` | `String` | ID в каталоге моделей |
| `custom_llm_provider` | `LowCardinality(String)` | `openai`, `ollama`, ... |
| `api_base` | `String` | URL эндпоинта (`https://api.proxyapi.ru/v1`) |

### Деньги и токены

| Колонка | Тип | Описание |
|---|---|---|
| `spend` | `Nullable(Float64) DEFAULT NULL` | Стоимость в $, `NULL` при фейле |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | `UInt32` | Токены |
| `cache_read_tokens` / `cache_write_tokens` | `UInt32` | Токены кэша |

### Время

| Колонка | Тип | Описание |
|---|---|---|
| `start_time` | `DateTime64(3)` | Начало (партиционирование) |
| `end_time` | `DateTime64(3)` | Конец (версия в ReplacingMergeTree) |
| `completion_start_time` | `Nullable(DateTime64(3))` | Начало генерации (TTFT) |

### Результат и наблюдаемость

| Колонка | Тип | Описание |
|---|---|---|
| `status` | `LowCardinality(String)` | `success` / `failure` |
| `error_str` | `String` | Текст ошибки (например, `400: {'error': '... Invalid model name ...'}`) |
| `cache_hit` | `Bool` | Попадание в кэш |
| `session_id` / `trace_id` / `span_id` | `String` | Трассировка |
| `request_tags` | `Array(String)` | Теги запроса |
| `metadata` | `String CODEC(ZSTD(3))` | Служебный JSON-объект |
| `messages` | `String CODEC(ZSTD(3))` | Весь промпт (JSON-массив) |
| `response` | `String CODEC(ZSTD(3))` | Ответ модели (JSON-объект) |
| `EngineReceivedMs` | `UInt64 DEFAULT 0` | Задержка до приёма движком |

## 5. Payload-колонки (подробно)

Включаются конфигом `store_prompts_in_spend_logs: true` (`litellm/config.yaml`).
Реальные размеры: `metadata` ~3.3–9.5 КБ, `messages` ~18 КБ–**800 КБ**,
`response` ~1.5–49 КБ, у фейлов `response = "{}"` (2 байта).

### 5.1 `metadata` — служебный JSON-объект (~50 полей)

Группы:

- **Снапшот VirtualKey** (`user_api_key_*`): `token`, `api_key`, `hash`, `spend`,
  `total_spend`, `models`, `aliases`, `config`, `user_id`, `metadata`,
  `allowed_cache_controls`, `allowed_routes`, `permissions`, `model_spend`,
  `model_max_budget`, `budget_fallbacks`, `soft_budget_cooldown`, `rotation_count`,
  `auto_rotate`, `team_models`, `team_blocked`, `last_refreshed_at`, `user_role`,
  `request_route`, `is_session_token`, `team_id`, `team_alias`,
  `object_permission_id`, `team_object_permission_id`, `end_user_max_budget`,
  `auth_metadata`.
- **Guardrails (Presidio)**: `standard_logging_guardrail_information` — массив вызовов
  `presidio-pii-mask` (`guardrail_name`, `guardrail_provider`,
  `guardrail_mode: pre_call|post_call`, `guardrail_status`, `start_time`, `end_time`,
  `duration`, `guardrail_response: [{entity_type, start, end, score}]`,
  `masked_entity_count: {US_SSN: 1}`); `_pre_call_executed_guardrails`
  (ID вида `9204b6c7...:presidio-pii-mask`), `applied_guardrails`.
- **Маршрутизация/цена**: `model_group`, `original_model_group`, `model_group_alias`,
  `deployment`, `deployment_model_name`, `api_base`,
  `model_info` (`{input_cost_per_token, output_cost_per_token, id, db_model,
  member_auto_router}`), `attempted_fallbacks`, `attempted_retries`, `max_retries`,
  `queue_time_seconds`, `kubernetes_pod_routing`, `caching_groups`, `routing_decision`.
- **Запрос**: `endpoint`, `user_agent`, `requester_ip_address`, `headers`,
  `requester_custom_headers`, `requester_metadata`
  (`{trace_id, headers, used_client_oauth_token}`), `used_client_oauth_token`,
  `trace_id`, `litellm_api_version`, `global_max_parallel_requests`,
  `cold_storage_object_key`.
- **Usage**: `usage_object` — `{completion_tokens, prompt_tokens, total_tokens,
  completion_tokens_details: {reasoning_tokens, ...},
  prompt_tokens_details: {cached_tokens, ...}, cost}`.
- **Внутренности провайдера**: `hidden_params` — `{provider_response_model,
  custom_llm_provider, created_at, model_id, api_base,
  additional_headers (заголовки ответа провайдера), response_cost, received_model_id}`.
- **Агент-поля**: `agent_id`, `actor_agent_id`, `target_agent_id`, `billing_agent_id`,
  `agent_execution_mode`, `verified_human_user_id`.
- **Прочее**: `_litellm_router_usage_counted_tokens`, `litellm_roi_estimator`,
  `litellm_lens_internal`, `spend_logs_metadata`, `prompt_management_metadata`,
  `mcp_tool_call_metadata`, `vector_store_request_metadata`, `team_id`, `team_alias`.

### 5.2 `messages` — JSON-массив (весь промпт)

Полный запрос на `chat/completions`. Элементы: `{role: system|user|assistant|tool,
content, name?, tool_calls?: [{id, type: "function", function: {name, arguments}}],
tool_call_id?, function_call?, reasoning_content?}`. Содержит системный промпт,
пользовательские сообщения, результаты tool-вызовов. Сохраняется и у фейловых записей.

### 5.3 `response` — JSON-объект (ответ модели)

OpenAI-совместимый: `{id, created, model, object: "chat.completion",
system_fingerprint, service_tier,
choices: [{finish_reason: stop|tool_calls|..., index,
message: {role: "assistant", content, tool_calls, function_call, reasoning_content}}],
usage: {prompt_tokens, completion_tokens, total_tokens, completion_tokens_details,
prompt_tokens_details, cost}}`. У фейлов — `{}`.


## 6. Поведение успешных vs фейловых записей

| Аспект | success | failure |
|---|---|---|
| `spend` | число, напр. `0.0075954` | `0.0` (или `NULL`) |
| Токены | реальные (`prompt=11912, completion=249`) | `0` |
| `response` | полный JSON | `{}` |
| `error_str` | пусто | текст ошибки |
| `provider`/`api_base` | заполнены | пусто (напр. `ollama/gemma4:26b`) |
| `messages` | сохраняется | тоже сохраняется (до 800 КБ!) |
| `cache_read_tokens` | напр. `6144` | `0` |

Реальный пример фейла: `3cd70f39-...`, `400: Invalid model name passed in
model=ollama/gemma4:26b` — ровно кейс решения №19 (gemma4:26b не зарегистрирована).

## 7. Кто читает и пишет

- **Пишет**: только LiteLLM (rust-bridge) под пользователем из `CLICKHOUSE_URL`
  (`default`). Агент в неё писать не может и не должен.
- **Читает**: Observer (`agent/src/agent/observer/observer.py`) через `agent_reader`
  — только производные витрины `security_logs.*` (`08_derived_views.sql`),
  напрямую в `litellm.spend_logs` не ходит (тяжёлая колонка `messages`):

  ```sql
  -- 1. spend_logs_extended: 1:1 со spend_logs + вычисляемые поля
  SELECT timestamp, user_id, end_user, api_base, model, model_group,
         custom_llm_provider, tool_calls_count, guardrails_count,
         requester_ip, user_agent
  FROM security_logs.spend_logs_extended
  WHERE timestamp >= now() - INTERVAL 30 MINUTE

  -- 2. events_tool_calls: сгруппированные вызовы инструментов
  SELECT tool_name, user_id, model, uniq(request_id) AS calls
  FROM security_logs.events_tool_calls
  WHERE timestamp >= now() - INTERVAL 30 MINUTE
  GROUP BY tool_name, user_id, model

  -- 3. events_guardrails: сгруппированные срабатывания гардрейлов
  SELECT guardrail_name, guardrail_provider, guardrail_mode, action,
         uniq(request_id) AS firings
  FROM security_logs.events_guardrails
  WHERE timestamp >= now() - INTERVAL 30 MINUTE
  GROUP BY guardrail_name, guardrail_provider, guardrail_mode, action
  ```

  Затем `extract_candidates` мапит: `api_base` → актив `external_api`,
  `user_id` → `ai_agent`, `end_user` → `user`, `tool_name` → `tool`,
  `guardrail_name` → `guardrail`, и пишет в `security_logs.asset_proposals`
  (права `agent_writer`, решение №16). Коррелятор прогоняет статические правила
  01–10; правила 06–10 читают те же витрины `security_logs.*`.

## 8. Нюансы и зоны риска (для размышления)

1. **TTL 14 дней** — исторические данные исчезают; если понадобится долгая
   аналитика — нужен отдельный архив.
2. **Payload = чувствительные данные**: в `messages`/`metadata` лежат полные
   промпты, ответы, снапшот ключей и PII. `REDACTED` / `<PHONE_NUMBER>` /
   `<US_SSN>` в выдачах — это маскировка MCP-шлюза при чтении, в самой таблице
   данные сырые. Поэтому правило AGENTS.md: перед записью в
   `alert_incidents.context` — обязательный Presidio-фильтр.
3. **Крупные `messages`** (до ~800 КБ) — тяжелые чтения `SELECT *` нежелательны;
   Observer читает только 6 колонок, и это правильно.
4. **Дубликаты при ReplacingMergeTree**: схлопывание по
   `(team_id, start_time, request_id)` асинхронное — без `FINAL`/`PREWHERE`
   возможны дубли; Observer при дедупликации кандидатов полагается на `setdefault`
   + проверку в `assets`/`asset_proposals`.
5. **`spend` при фейлах** = `0.0`/`NULL` — при подсчёте общих затрат нужно
   фильтровать по `status='success'`.
6. **Зависимость от `main-latest`**: схема (37 колонок, миграции v6–v16) привязана
   к конкретной версии образа `ghcr.io/berriai/litellm:main-latest`; обновление
   образа может менять схему (миграции применяет `make ch-ensure`).
7. **`cache_read_tokens` ≠ 0 при `cache_hit=false`** — судя по примерам, кэш-токены
   фиксируются и при промахах (промпт-кэш провайдера), это стоит учитывать в правилах.

