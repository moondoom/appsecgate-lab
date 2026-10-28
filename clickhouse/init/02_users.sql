-- Пользователи создаются через environment-переменные ClickHouse
-- Этот файл — заглушка; пароли задаются через CLICKHOUSE_DEFAULT_ACCESS_MANAGEMENT.
-- Для production используйте XML-конфиги или SQL-команды с паролями.

-- agent_reader — read-only для agent (исследование)
CREATE USER IF NOT EXISTS agent_reader IDENTIFIED BY '${AGENT_READER_PASS}'
SETTINGS max_execution_time = 60, max_memory_usage = 2000000000;
GRANT SELECT ON security_logs.* TO agent_reader;
GRANT SELECT ON system.* TO agent_reader;
GRANT SELECT ON litellm.* TO agent_reader;

-- agent_writer — запись только в proposals и memory
CREATE USER IF NOT EXISTS agent_writer IDENTIFIED BY '${AGENT_WRITER_PASS}';
GRANT INSERT ON security_logs.rule_proposals TO agent_writer;
GRANT INSERT ON security_logs.asset_proposals TO agent_writer;
GRANT INSERT ON security_logs.agent_memory TO agent_writer;
GRANT SELECT ON security_logs.rule_proposals TO agent_writer;
GRANT SELECT ON security_logs.asset_proposals TO agent_writer;
GRANT SELECT ON security_logs.agent_memory TO agent_writer;

-- agent_promoter — промоушен правил
CREATE USER IF NOT EXISTS agent_promoter IDENTIFIED BY '${AGENT_PROMOTER_PASS}';
GRANT INSERT ON security_logs.alert_rules TO agent_promoter;
GRANT INSERT ON security_logs.alert_incidents TO agent_promoter;
GRANT SELECT ON security_logs.rule_proposals TO agent_promoter;
GRANT SELECT ON security_logs.asset_proposals TO agent_promoter;
GRANT INSERT ON security_logs.agent_memory TO agent_promoter;
GRANT CREATE VIEW ON security_logs.* TO agent_promoter;
GRANT SELECT ON security_logs.* TO agent_promoter;

-- vector — приём auditd
CREATE USER IF NOT EXISTS vector IDENTIFIED BY '${VECTOR_PASS}';
GRANT INSERT ON security_logs.audit_events TO vector;
GRANT INSERT ON security_logs.assets TO vector;

-- otel — приём трейсов
CREATE USER IF NOT EXISTS otel IDENTIFIED BY '${OTEL_PASS}';
GRANT INSERT ON security_logs.agent_tool_calls TO otel;
GRANT INSERT ON security_logs.assets TO otel;
GRANT INSERT ON security_logs.mcp_tools TO otel;
GRANT INSERT ON security_logs.asset_tool_bindings TO otel;

-- grafana — визуализация
CREATE USER IF NOT EXISTS grafana IDENTIFIED BY '${GRAFANA_CH_PASS}';
GRANT SELECT ON security_logs.* TO grafana;
GRANT SELECT ON litellm.* TO grafana;
