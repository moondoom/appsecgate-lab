-- Unknown AI agent (more than 5 calls)
-- Source: §8.4 source.md
SELECT
    t.agent_name,
    min(t.timestamp) AS first_seen,
    count() AS calls,
    'medium' AS severity,
    count() AS triggered_value,
    format('{{"agent":"{}","first_seen":"{}","calls":{}}}',
        t.agent_name, min(t.timestamp), count()) AS context
FROM security_logs.agent_tool_calls AS t
LEFT JOIN security_logs.assets AS a
    ON 'agent:' || t.agent_name = a.asset_key
WHERE a.asset_id IS NULL
  AND t.timestamp >= now() - INTERVAL 1 HOUR
GROUP BY t.agent_name
HAVING calls > 5
ORDER BY calls DESC
SETTINGS join_use_nulls = 1
