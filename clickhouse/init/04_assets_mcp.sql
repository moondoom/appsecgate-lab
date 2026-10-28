-- Инвентарь активов
CREATE TABLE IF NOT EXISTS security_logs.assets (
    asset_id          UUID DEFAULT generateUUIDv4(),
    asset_key         String,
    asset_type        LowCardinality(String),    -- host, container, vm, ai_agent, chat, user, repo, database, external_api
    asset_subtype     LowCardinality(String),
    display_name      String,
    parent_asset_id   Nullable(UUID),
    owner             String DEFAULT '',
    criticality       LowCardinality(String) DEFAULT 'unknown',
    attributes        String DEFAULT '{}',
    first_seen        DateTime DEFAULT now(),
    last_seen         DateTime DEFAULT now(),
    observation_count UInt64 DEFAULT 1,
    source_of_truth   LowCardinality(String),    -- observed, declared, both
    is_active         UInt8 DEFAULT 1,
    updated_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (asset_type, asset_key)
TTL updated_at + INTERVAL 180 DAY;

-- MCP-серверы
CREATE TABLE IF NOT EXISTS security_logs.mcp_servers (
    server_id         UUID DEFAULT generateUUIDv4(),
    server_key        String,              -- 'server:<name>' or 'server:<host>:<port>'
    display_name      String,
    transport         LowCardinality(String), -- stdio, streamable_http
    endpoint          String,
    first_seen        DateTime DEFAULT now(),
    last_seen         DateTime DEFAULT now(),
    observation_count UInt64 DEFAULT 1,
    source_of_truth   LowCardinality(String) DEFAULT 'observed',
    is_active         UInt8 DEFAULT 1,
    updated_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (server_key);

-- MCP-инструменты
CREATE TABLE IF NOT EXISTS security_logs.mcp_tools (
    tool_id           UUID DEFAULT generateUUIDv4(),
    tool_key          String,              -- 'tool:<server_key>:<tool_name>'
    tool_name         String,
    tool_description  String DEFAULT '',
    input_schema      String DEFAULT '{}', -- JSON Schema
    server_key        String,
    first_seen        DateTime DEFAULT now(),
    last_seen         DateTime DEFAULT now(),
    observation_count UInt64 DEFAULT 1,
    is_active         UInt8 DEFAULT 1,
    updated_at        DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (server_key, tool_name);

-- Связи актив ↔ инструмент
CREATE TABLE IF NOT EXISTS security_logs.asset_tool_bindings (
    binding_id       UUID DEFAULT generateUUIDv4(),
    asset_key        String,
    tool_key         String,
    binding_source   LowCardinality(String), -- prompt_manifest, observed_call
    first_seen       DateTime DEFAULT now(),
    last_seen        DateTime DEFAULT now(),
    call_count       UInt64 DEFAULT 0,
    error_count      UInt64 DEFAULT 0,
    updated_at       DateTime DEFAULT now()
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (asset_key, tool_key);
