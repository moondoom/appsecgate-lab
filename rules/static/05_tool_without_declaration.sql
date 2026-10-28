-- Вызов MCP-инструмента без декларации в промпте
-- Источник: §6.3, паттерн 1 source.md
SELECT
    b.asset_key AS agent_asset,
    b.tool_key,
    t.tool_name,
    b.call_count,
    'high' AS severity,
    b.call_count AS triggered_value,
    format('{{"agent":"{}","tool":"{}","call_count":{}}}',
        b.asset_key, t.tool_name, b.call_count) AS context
FROM security_logs.asset_tool_bindings AS b
INNER JOIN security_logs.mcp_tools AS t ON b.tool_key = t.tool_key
WHERE b.binding_source = 'observed_call'
  AND b.call_count > 0
  AND NOT EXISTS (
      SELECT 1 FROM security_logs.asset_tool_bindings AS d
      WHERE d.asset_key = b.asset_key
        AND d.tool_key = b.tool_key
        AND d.binding_source = 'prompt_manifest'
  )
  AND b.last_seen > now() - INTERVAL 10 MINUTE
ORDER BY b.call_count DESC
