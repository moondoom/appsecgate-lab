-- Предложения правил
CREATE TABLE IF NOT EXISTS security_logs.rule_proposals (
    proposal_id     UUID DEFAULT generateUUIDv4(),
    proposed_query  String,
    rationale       String,
    hit_rate_sample Float64,
    estimated_cost  Float64,
    status          LowCardinality(String) DEFAULT 'draft',  -- draft, validated, approved, rejected, promoted
    validation_log  String,
    created_at      DateTime DEFAULT now(),
    updated_at      DateTime DEFAULT now(),
    reviewed_at     Nullable(DateTime),
    reviewed_by     LowCardinality(String) DEFAULT ''
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (proposal_id);  -- ключ уникален: (status, created_at) схлопывал батч-вставки одной секунды

-- Предложения по активам
CREATE TABLE IF NOT EXISTS security_logs.asset_proposals (
    proposal_id     UUID DEFAULT generateUUIDv4(),
    action          LowCardinality(String),     -- create, deactivate, update_owner, update_criticality
    asset_key       String,
    proposed_data   String,                     -- JSON
    rationale       String,
    confidence      Float64,
    status          LowCardinality(String) DEFAULT 'draft',
    created_at      DateTime DEFAULT now(),
    updated_at      DateTime DEFAULT now(),
    reviewed_at     Nullable(DateTime)
) ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (proposal_id);  -- ключ уникален: (status, created_at) схлопывал батч-вставки одной секунды

-- Память агента (отклонённые идеи, выученные паттерны)
CREATE TABLE IF NOT EXISTS security_logs.agent_memory (
    memory_id       UUID DEFAULT generateUUIDv4(),
    memory_type     LowCardinality(String),     -- rejected_rule, rejected_asset, learned_pattern, feedback
    content         String,                     -- JSON
    embedding       Array(Float32),
    created_at      DateTime DEFAULT now()
) ENGINE = MergeTree()
ORDER BY (memory_type, created_at)
TTL created_at + INTERVAL 365 DAY;
