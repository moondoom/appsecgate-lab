-- PII в трафике: пресидио-гардрейл замаскировал чувствительные сущности
-- Источник: security_logs.events_guardrails (витрина из litellm.spend_logs)
SELECT
    e.guardrail_name,
    e.guardrail_mode,
    e.entity_types,
    count() AS pii_events,
    'medium' AS severity,
    count() AS triggered_value,
    format('{{"guardrail":"{}","mode":"{}","entities":"{}","events":{}}}',
        e.guardrail_name, e.guardrail_mode,
        arrayStringConcat(e.entity_types, ','), count()) AS context
FROM security_logs.events_guardrails AS e
WHERE e.timestamp >= now() - INTERVAL 5 MINUTE
  AND length(e.entity_types) > 0
GROUP BY e.guardrail_name, e.guardrail_mode, e.entity_types
ORDER BY pii_events DESC
