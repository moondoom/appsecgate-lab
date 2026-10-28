-- Правила и инциденты
CREATE TABLE IF NOT EXISTS security_logs.alert_rules (
    rule_id         UUID DEFAULT generateUUIDv4(),
    rule_name       String,
    query           String,
    severity        LowCardinality(String),
    rule_kind       LowCardinality(String),     -- periodic, materialized_view
    check_interval  UInt32 DEFAULT 60,
    is_active       UInt8 DEFAULT 1,
    created_by      LowCardinality(String),     -- human, agent
    created_at      DateTime DEFAULT now(),
    last_evaluated  DateTime,
    last_hit        Nullable(DateTime)
) ENGINE = MergeTree()
ORDER BY (severity, rule_id);

CREATE TABLE IF NOT EXISTS security_logs.alert_incidents (
    incident_id     UUID DEFAULT generateUUIDv4(),
    rule_id         UUID,
    rule_name       String,
    triggered_value Float64,
    severity        LowCardinality(String),
    context         String,                     -- JSON с evidence
    triggered_at    DateTime DEFAULT now(),
    resolved_at     Nullable(DateTime),
    disposition     LowCardinality(String) DEFAULT 'open',
    disposition_by  LowCardinality(String) DEFAULT ''
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(triggered_at)
ORDER BY (severity, triggered_at)
TTL triggered_at + INTERVAL 365 DAY;
