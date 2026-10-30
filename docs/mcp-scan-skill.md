# MCP skill: security scanning

Paste this block at the start of any task in Act mode.
No local scanners — only AppSecGate MCP tools.

---

## 1. Scanning

```
after editing a file → appsecgate-lab__scan_file(path=<file>)
before committing   → appsecgate-lab__scan_diff()
after a stage       → appsecgate-lab__scan_project()
```

## 2. Handling findings

```
found → appsecgate-lab__get_fix_context(finding_id=<id>)
       → read the code, fix it
       → appsecgate-lab__verify_fix(finding_id=<id>, status="fixed")

false positive → appsecgate-lab__submit_feedback(
                     finding_id=<id>,
                     type="FALSE_POSITIVE",
                     reason="why this is not a vulnerability"
                 )

not fixing yet  → appsecgate-lab__suppress_finding(
                     finding_id=<id>,
                     reason="why it was deferred",
                     expires_at="2026-12-31"
                 )
```

## 3. Rules

1. After editing **any** file → `scan_file`. Do not skip it.
2. `scan_diff` — before every commit. No exceptions.
3. Findings `critical`/`high` — fix immediately. `medium` — fix or `submit_feedback`.
4. `submit_feedback` without a reason is rejected by the system.
5. `suppress` — only with `expires_at`. No indefinite suppressions.
6. At the end of a stage — `scan_project`. Must be 0 active findings of level `>= medium`.

## 4. Useful database queries

```sql
-- All open high/critical
SELECT logical_id, severity, file_path, rule_name
FROM v_findings
WHERE status = 'SHOWN' AND severity IN ('high', 'critical')
ORDER BY severity

-- Statistics by file
SELECT file_path, severity, count(*) AS n
FROM v_findings
WHERE status = 'SHOWN'
GROUP BY file_path, severity
ORDER BY n DESC

-- Scan history for a file
-- (via appsecgate-lab__get_scan_history, not SQL)
```

## 5. MCP tools (cheat sheet)

| Tool | When |
| :--- | :--- |
| `scan_file` | After editing a file |
| `scan_diff` | Before committing |
| `scan_project` | After a stage |
| `get_fix_context` | A finding exists — get the context |
| `verify_fix` | After fixing — confirm |
| `submit_feedback` | False positive |
| `suppress_finding` | Deferred fix (with a date) |
| `get_scan_history` | See what happened |
| `query_findings_db` | Arbitrary SELECT over v_findings |
