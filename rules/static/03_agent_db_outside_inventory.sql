-- AI agent accesses DB outside inventory
-- Source: §8.3 source.md
SELECT
    t.trace_id,
    t.agent_name,
    t.tool_name,
    t.arguments AS db_connection,
    t.timestamp,
    'high' AS severity,
    1 AS triggered_value,
    format('{{"trace_id":"{}","agent":"{}","tool":"{}","connection":"{}"}}',
        t.trace_id, t.agent_name, t.tool_name, t.arguments) AS context
FROM security_logs.agent_tool_calls AS t
LEFT JOIN security_logs.assets AS a
    ON 'db:' || extractDbKey(t.arguments) = a.asset_key
    AND a.asset_type = 'database'
    AND a.source_of_truth IN ('declared', 'both')
WHERE a.asset_id IS NULL
  AND t.tool_name IN ('query_database', 'psql', 'mysql', 'mongo_query')
  AND t.timestamp >= now() - INTERVAL 10 MINUTE
ORDER BY t.timestamp DESC
SETTINGS join_use_nulls = 1
