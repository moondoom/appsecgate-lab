-- Вызов инструмента, которого нет ни в mcp_tools, ни в инвентаре (тип tool)
-- Источник: security_logs.events_tool_calls (витрина из litellm.spend_logs)
SELECT
    e.tool_name,
    e.user_id,
    uniq(e.request_id) AS calls,
    'medium' AS severity,
    uniq(e.request_id) AS triggered_value,
    format('{{"tool":"{}","agent":"{}","calls":{}}}',
        e.tool_name, e.user_id, uniq(e.request_id)) AS context
FROM security_logs.events_tool_calls AS e
LEFT JOIN security_logs.mcp_tools AS m
    ON e.tool_name = m.tool_name
LEFT JOIN security_logs.assets AS a
    ON 'tool:' || e.tool_name = a.asset_key
    AND a.asset_type = 'tool'
WHERE e.timestamp >= now() - INTERVAL 10 MINUTE
  AND m.tool_id IS NULL
  AND a.asset_id IS NULL
GROUP BY e.tool_name, e.user_id
ORDER BY calls DESC
SETTINGS join_use_nulls = 1
