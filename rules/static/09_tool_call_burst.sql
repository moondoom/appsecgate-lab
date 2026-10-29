-- Всплеск вызовов инструмента одним агентом (потенциально зациклившийся агент)
-- Источник: security_logs.events_tool_calls (витрина из litellm.spend_logs)
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
