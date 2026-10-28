# MCP-скилл: сканирование безопасности

Копируй этот блок в начало любой задачи в Act mode.
Никаких локальных сканеров — только инструменты AppSecGate MCP.

---

## 1. Сканирование

```
после правки файла → appsecgate-lab__scan_file(path=<файл>)
перед коммитом     → appsecgate-lab__scan_diff()
после этапа        → appsecgate-lab__scan_project()
```

## 2. Обработка находок

```
найдено → appsecgate-lab__get_fix_context(finding_id=<id>)
         → читаешь код, правишь
         → appsecgate-lab__verify_fix(finding_id=<id>, status="fixed")

ложное срабатывание → appsecgate-lab__submit_feedback(
                          finding_id=<id>,
                          type="FALSE_POSITIVE",
                          reason="почему это не уязвимость"
                      )

временно не чинишь  → appsecgate-lab__suppress_finding(
                          finding_id=<id>,
                          reason="почему отложили",
                          expires_at="2026-12-31"
                      )
```

## 3. Правила

1. После правки **любого** файла → `scan_file`. Не пропускай.
2. `scan_diff` — перед каждым коммитом. Без исключений.
3. Находки `critical`/`high` — fix сразу. `medium` — fix или `submit_feedback`.
4. `submit_feedback` без причины отклоняется системой.
5. `suppress` — только с `expires_at`. Бессрочных подавлений нет.
6. В конце этапа — `scan_project`. Должен быть 0 активных findings уровня `>= medium`.

## 4. Полезные запросы в БД

```sql
-- Все открытые high/critical
SELECT logical_id, severity, file_path, rule_name
FROM v_findings
WHERE status = 'SHOWN' AND severity IN ('high', 'critical')
ORDER BY severity

-- Статистика по файлам
SELECT file_path, severity, count(*) AS n
FROM v_findings
WHERE status = 'SHOWN'
GROUP BY file_path, severity
ORDER BY n DESC

-- История сканирования по файлу
-- (через appsecgate-lab__get_scan_history, не SQL)
```

## 5. Инструменты MCP (шпаргалка)

| Инструмент | Когда |
| :--- | :--- |
| `scan_file` | После правки файла |
| `scan_diff` | Перед коммитом |
| `scan_project` | После этапа |
| `get_fix_context` | Есть находка — получи контекст |
| `verify_fix` | После исправления — подтверди |
| `submit_feedback` | Ложное срабатывание |
| `suppress_finding` | Отложил фикс (с датой) |
| `get_scan_history` | Посмотреть что было |
| `query_findings_db` | Произвольный SELECT по v_findings |
