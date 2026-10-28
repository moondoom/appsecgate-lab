-- Shadow IT: наблюдаемый хост без декларации
-- Источник: §8.2 source.md
SELECT
    a.asset_key AS host,
    a.last_seen,
    'high' AS severity,
    1 AS triggered_value,
    format('{{"host":"{}","last_seen":"{}","observation_count":{}}}',
        a.asset_key, a.last_seen, a.observation_count) AS context
FROM security_logs.assets AS a
WHERE a.asset_type = 'host'
  AND a.source_of_truth = 'observed'
  AND a.last_seen > now() - INTERVAL 1 HOUR
  AND NOT EXISTS (
    SELECT 1 FROM security_logs.assets AS d
    WHERE d.asset_key = a.asset_key
      AND d.source_of_truth IN ('declared', 'both')
  )
ORDER BY a.last_seen DESC
