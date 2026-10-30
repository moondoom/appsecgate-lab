-- Tool call burst by a single agent (possibly looped agent)
-- Source: security_logs.events_tool_calls (view from litellm.spend_logs)
SELECT
    e.user_id,
    e.tool_name,
    count() AS calls,
    'medium' AS severity,
    count() AS triggered_value,
    format('{{"agent":"{}","tool":"{}","calls":{}}}',
        e.user_id, e.tool_name, count()) AS context
FROM security_logs.events_tool_calls AS e
WHERE e.timestamp >= now() - INTERVAL 10 MINUTE
GROUP BY e.user_id, e.tool_name
HAVING calls > 100
ORDER BY calls DESC
