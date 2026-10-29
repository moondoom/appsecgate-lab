-- Гардрейл отработал неожиданно: действие не MASK или статус не success
-- Источник: security_logs.events_guardrails (витрина из litellm.spend_logs)
SELECT
    e.guardrail_name,
    e.guardrail_provider,
    e.guardrail_mode,
    e.action,
    e.status,
    count() AS n,
    'high' AS severity,
    count() AS triggered_value,
    format('{{"guardrail":"{}","provider":"{}","mode":"{}","action":"{}","status":"{}","events":{}}}',
        e.guardrail_name, e.guardrail_provider, e.guardrail_mode,
        e.action, e.status, count()) AS context
FROM security_logs.events_guardrails AS e
WHERE e.timestamp >= now() - INTERVAL 10 MINUTE
  AND (e.action != 'MASK' OR e.status != 'success')
GROUP BY e.guardrail_name, e.guardrail_provider, e.guardrail_mode, e.action, e.status
ORDER BY n DESC
