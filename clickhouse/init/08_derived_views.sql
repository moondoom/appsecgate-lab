-- ==============================================================================
-- 08_derived_views.sql
-- Производные витрины из litellm.spend_logs.
-- Сверено с реальной схемой и живыми данными стенда 29.10.2026
-- (см. docs/spend-logs.md; LiteLLM main-latest, API v1.109.0).
--
-- Три целевые таблицы + три материализованных представления (MV). MV наполняют
-- таблицы только при НОВЫХ вставках в spend_logs (пишет сам LiteLLM) — уже
-- существующие строки (~267) не бэкфилятся.
-- Если витрину нужно наполнить историей вручную, защищайтесь от дублей:
-- MV уже обработал часть строк к моменту бэкфилла, поэтому INSERT должен
-- отсекать существующие request_id, например:
--   INSERT INTO security_logs.spend_logs_extended SELECT ... FROM litellm.spend_logs
--   WHERE start_time >= now() - INTERVAL 14 DAY
--     AND request_id NOT IN (SELECT request_id FROM security_logs.spend_logs_extended);
-- (без этого строки, попавшие в витрину через MV, будут вставлены повторно).
--
-- Скрипт идемпотентен (IF NOT EXISTS) — повторное применение через
-- `make ch-init` безопасно.
--
-- TTL = 14 дней во всех витринах синхронизирован с TTL источника
-- (spend_logs: toDateTime(start_time) + toIntervalDay(14), см. §3 отчёта).
--
-- ВНИМАНИЕ (только для свежего volume): docker-entrypoint-initdb.d выполнит этот
-- файл ДО `make ch-ensure` (который создаёт spend_logs), и CREATE MV упадёт
-- (в /entrypoint.sh стоит `set -eo pipefail` — контейнер не поднимется).
-- Применяйте файл через `make ch-init` на стенде, где spend_logs уже создана,
-- либо на свежем стенде после `make ch-ensure`.
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- 1. СОБЫТИЯ: ВЫЗОВЫ ИНСТРУМЕНТОВ (TOOL CALLS)
--    Одна строка = один вызов инструмента: ARRAY JOIN по messages[].tool_calls.
--    status — статус запроса целиком: per-tool-call статусов в messages нет,
--    а хардкод 'success' врал бы для фейловых запросов (messages пишутся и при
--    ошибках, см. §6 отчёта).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_logs.events_tool_calls (
    timestamp     DateTime64(3, 'UTC'),
    request_id    String,
    model         LowCardinality(String),
    user_id       String,
    tool_call_id  String,
    tool_name     LowCardinality(String),
    arguments     String,
    status        LowCardinality(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, tool_name)
TTL timestamp + INTERVAL 14 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS security_logs.mv_events_tool_calls
TO security_logs.events_tool_calls
AS
SELECT
    start_time AS timestamp,
    request_id,
    model,
    user AS user_id,
    JSONExtractString(tool_call, 'id') AS tool_call_id,
    JSONExtractString(tool_call, 'function', 'name') AS tool_name,
    JSONExtractString(tool_call, 'function', 'arguments') AS arguments,
    status
FROM litellm.spend_logs
ARRAY JOIN JSONExtractArrayRaw(messages) AS msg
ARRAY JOIN JSONExtractArrayRaw(msg, 'tool_calls') AS tool_call
WHERE JSONExtractString(msg, 'role') = 'assistant'
  AND JSONHas(msg, 'tool_calls');

-- ------------------------------------------------------------------------------
-- 2. СОБЫТИЯ: СРАБОТКИ ГАРДРЕЙЛОВ (GUARDRAILS)
--    Источник: metadata.standard_logging_guardrail_information — массив записей
--    вида {guardrail_name, guardrail_provider, guardrail_mode, guardrail_status,
--    duration, guardrail_response: [{entity_type, start, end, score}],
--    masked_entity_count: {TYPE: n}}.
--    Поле action в данных LiteLLM отсутствует (проверено: 0/57 записей) —
--    пустая строка заменяется дефолтом 'MASK' (empty(), т.к. coalesce не ловит '').
--    guardrail_mode приходит двумя форматами: строкой ("pre_call") или
--    JSON-массивом (["post_call"], 210/3834 записей) — снимаем обёртку
--    ["..."] через regex (JSONExtractArrayRaw отдаёт элементы с кавычками,
--    JSONPath-индексы этой версией не поддерживаются).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_logs.events_guardrails (
    timestamp           DateTime64(3, 'UTC'),
    request_id          String,
    model               LowCardinality(String),
    user_id             String,
    guardrail_name      LowCardinality(String),
    guardrail_provider  LowCardinality(String),
    guardrail_mode      LowCardinality(String),
    action              LowCardinality(String),
    duration_ms         Float64,
    masked_entity_counts String,            -- JSON-объект {TYPE: count}, напр. {"US_SSN":1}
    entity_types        Array(String),
    status              LowCardinality(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, guardrail_name)
TTL timestamp + INTERVAL 14 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS security_logs.mv_events_guardrails
TO security_logs.events_guardrails
AS
SELECT
    start_time AS timestamp,
    request_id,
    model,
    user AS user_id,
    JSONExtractString(guardrail, 'guardrail_name') AS guardrail_name,
    JSONExtractString(guardrail, 'guardrail_provider') AS guardrail_provider,
    replaceRegexpOne(JSONExtractString(guardrail, 'guardrail_mode'),
                     '^\\["([^"]*)"\\]$', '\\1') AS guardrail_mode,
    if(empty(JSONExtractString(guardrail, 'action')),
       'MASK',
       JSONExtractString(guardrail, 'action')) AS action,
    JSONExtractFloat(guardrail, 'duration') * 1000 AS duration_ms,
    JSONExtractRaw(guardrail, 'masked_entity_count') AS masked_entity_counts,
    arrayMap(x -> JSONExtractString(x, 'entity_type'),
             JSONExtractArrayRaw(guardrail, 'guardrail_response')) AS entity_types,
    JSONExtractString(guardrail, 'guardrail_status') AS status
FROM litellm.spend_logs
ARRAY JOIN JSONExtractArrayRaw(metadata, 'standard_logging_guardrail_information') AS guardrail
WHERE JSONHas(metadata, 'standard_logging_guardrail_information')
  AND length(JSONExtractArrayRaw(metadata, 'standard_logging_guardrail_information')) > 0;

-- ------------------------------------------------------------------------------
-- 3. РАСШИРЕННЫЙ SPEND_LOGS (1:1, одна строка на запрос)
--    Дополняет исходную таблицу вычисляемыми полями:
--      ttft_ms          — время до первого токена (датаDiff в мс, >= 0);
--      tool_calls_count — всего вызовов инструментов по всем messages;
--      guardrails_count — всего срабатываний guardrail'ов;
--      requester_ip / user_agent — из metadata;
--      request_tags     — верхнеуровневая колонка spend_logs (в metadata его НЕТ,
--                         проверено на живых данных: 0/296 строк);
--      trace_id         — metadata.trace_id (W3C) с фолбэком на колонку trace_id
--                         (верхнеуровневая trace_id в данных пустая).
-- ------------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS security_logs.spend_logs_extended (
    request_id            String,
    trace_id              String,
    response_id           String,
    timestamp             DateTime64(3, 'UTC'),
    end_time              DateTime64(3, 'UTC'),
    completion_start_time Nullable(DateTime64(3, 'UTC')),
    ttft_ms               UInt32,

    user_id               String,
    end_user              String,
    api_key               String,
    team_id               String,

    model                 LowCardinality(String),
    model_group           LowCardinality(String),
    api_base              String,
    custom_llm_provider   LowCardinality(String),

    cost                  Float64,
    prompt_tokens         UInt32,
    completion_tokens     UInt32,
    total_tokens          UInt32,
    cache_read_tokens     UInt32,
    cache_write_tokens    UInt32,
    cache_hit             Bool,

    status                LowCardinality(String),
    error_str             String,

    tool_calls_count      UInt32,
    guardrails_count      UInt32,

    requester_ip          String,
    user_agent            String,
    request_tags          Array(String)
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (timestamp, request_id)
TTL timestamp + INTERVAL 14 DAY;

CREATE MATERIALIZED VIEW IF NOT EXISTS security_logs.mv_spend_logs_extended
TO security_logs.spend_logs_extended
AS
SELECT
    request_id,
    if(empty(JSONExtractString(metadata, 'trace_id')),
       trace_id,
       JSONExtractString(metadata, 'trace_id')) AS trace_id,
    response_id,
    start_time AS timestamp,
    end_time,
    completion_start_time,
    if(isNull(completion_start_time),
       0,
       greatest(0, dateDiff('millisecond', start_time, completion_start_time))) AS ttft_ms,

    user AS user_id,
    end_user,
    api_key,
    team_id,

    model,
    model_group,
    api_base,
    custom_llm_provider,

    ifNull(spend, 0.0) AS cost,
    prompt_tokens,
    completion_tokens,
    total_tokens,
    cache_read_tokens,
    cache_write_tokens,
    cache_hit,

    status,
    error_str,

    length(arrayFlatten(arrayMap(msg -> JSONExtractArrayRaw(msg, 'tool_calls'),
                                 JSONExtractArrayRaw(messages)))) AS tool_calls_count,
    length(JSONExtractArrayRaw(metadata, 'standard_logging_guardrail_information')) AS guardrails_count,

    JSONExtractString(metadata, 'requester_ip_address') AS requester_ip,
    JSONExtractString(metadata, 'user_agent') AS user_agent,
    request_tags
FROM litellm.spend_logs;

