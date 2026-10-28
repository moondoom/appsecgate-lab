-- Системный аудит с соседних хостов
CREATE TABLE IF NOT EXISTS security_logs.audit_events (
    timestamp       DateTime64(3, 'UTC'),
    source_host     LowCardinality(String),
    type            LowCardinality(String),     -- SYSCALL, EXECVE, CONNECT, PATH
    pid             UInt32,
    ppid            UInt32,
    uid             UInt32,
    exe             String,
    exe_args        String,
    key             LowCardinality(String),
    success         UInt8,
    trace_id        String DEFAULT '',
    session_id      String DEFAULT '',
    asset_key       String DEFAULT ''
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (source_host, timestamp, pid)
TTL timestamp + INTERVAL 90 DAY;

-- Действия AI-агента (tool calls, LLM calls)
CREATE TABLE IF NOT EXISTS security_logs.agent_tool_calls (
    timestamp       DateTime64(3, 'UTC'),
    trace_id        String,
    span_id         String,
    session_id      String,
    user_id         String,
    agent_name      LowCardinality(String),
    step            UInt32,
    event_type      LowCardinality(String),     -- tool_call, tool_result, llm_call
    tool_name       LowCardinality(String),
    arguments       String,                     -- JSON
    result_summary  String,
    status          LowCardinality(String),
    error_type      LowCardinality(String) DEFAULT '',
    latency_ms      UInt64,
    input_tokens    UInt32,
    output_tokens   UInt32,
    error_message   String,
    source_host     String
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(timestamp)
ORDER BY (trace_id, timestamp)
TTL timestamp + INTERVAL 90 DAY;
