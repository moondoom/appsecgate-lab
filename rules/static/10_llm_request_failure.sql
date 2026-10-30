-- LLM request failures through the proxy (view spend_logs_extended)
-- Source: security_logs.spend_logs_extended (view from litellm.spend_logs)
SELECT
    e.request_id,
    e.model,
    e.status,
    e.error_str,
    'high' AS severity,
    1 AS triggered_value,
    format('{{"request_id":"{}","model":"{}","error":"{}"}}',
        e.request_id, e.model, e.error_str) AS context
FROM security_logs.spend_logs_extended AS e
WHERE e.status = 'failure'
  AND e.timestamp >= now() - INTERVAL 30 MINUTE
ORDER BY e.timestamp DESC
