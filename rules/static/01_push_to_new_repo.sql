-- Push to new repository (unknown in inventory)
-- Source: §8.1 source.md
SELECT
    e.trace_id,
    e.source_host,
    e.exe,
    extractRepoUrl(e.exe_args) AS repo_url,
    e.timestamp AS push_time,
    CASE
        WHEN a.asset_id IS NULL THEN 'high'
        WHEN a.criticality = 'critical' THEN 'high'
        ELSE 'medium'
    END AS severity,
    1 AS triggered_value,
    format('{{"trace_id":"{}","source_host":"{}","repo_url":"{}","push_time":"{}"}}',
        e.trace_id, e.source_host, extractRepoUrl(e.exe_args), e.timestamp) AS context
FROM security_logs.audit_events AS e
LEFT JOIN security_logs.assets AS a
    ON 'repo:' || normalizeRepoUrl(extractRepoUrl(e.exe_args)) = a.asset_key
    AND a.asset_type = 'repo'
WHERE e.exe LIKE '%git%push%'
  AND extractRepoUrl(e.exe_args) != ''
  AND e.timestamp >= now() - INTERVAL 5 MINUTE
  AND a.asset_id IS NULL
ORDER BY e.timestamp DESC
SETTINGS join_use_nulls = 1
