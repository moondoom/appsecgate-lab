#!/usr/bin/env python3
"""Скрипт генерации Grafana-дашбордов AppSecGate (stdlib only, без зависимостей).

Выход (коммитится вместе со скриптом):
  grafana/provisioning/dashboards/agent-activity-control.json  — «Агент: контроль действий»
  grafana/provisioning/dashboards/raw-views-explorer.json      — «Сырые данные из view»

Запуск: python3 scripts/gen_dashboards.py   (или `make dashboards`)

Веб-график смонтирован на `./grafana/provisioning:/etc/grafana/provisioning`,
поэтому JSON ложатся рядом с provider-конфигом dashboards.yml.

Все запросы — только SELECT по `security_logs.*` (в духе вайтлиста Validator).
Макросы плагина grafana-clickhouse-datasource:
  $__timeFilter(col)           — фильтр по времени дашборда
  $__timeInterval(col)         — бакетизация по $__interval
  $__conditionalAll(col, $var) — подстановка переменной / 1=1 для «All»
"""

from __future__ import annotations

import json
from pathlib import Path

CH = {"type": "grafana-clickhouse-datasource", "uid": "PDEE91DDB90597936"}
PROM = {"type": "prometheus", "uid": "PBFA97CFB590B2093"}

OUT_DIR = Path(__file__).resolve().parent.parent / "grafana" / "provisioning" / "dashboards"


# ---------------------------------------------------------------------------
# Базовые помощники
# ---------------------------------------------------------------------------


def target_ch(sql: str, fmt: int = 1, ref: str = "A") -> dict:
    """fmt: 0 = time series, 1 = table."""
    return {
        "refId": ref,
        "datasource": CH,
        "rawQuery": True,
        "rawSql": sql,
        "format": fmt,
        "database": "security_logs",
        "queryType": "sql",
        "editorMode": "sql",
    }


def target_prom(expr: str, ref: str = "A") -> dict:
    return {
        "refId": ref,
        "datasource": PROM,
        "expr": expr,
        "range": True,
        "instant": True,
        "format": "time_series",
    }


# Колонки времени в таблицах — выставляем формат даты при показе.
_TIME_COLS = (
    "timestamp",
    "triggered_at",
    "first_seen",
    "last_seen",
    "created_at",
    "updated_at",
    "last_evaluated",
    "last_hit",
)


def _overrides(unit_cols: dict[str, str]) -> list[dict]:
    overrides = [
        {
            "matcher": {"id": "byName", "options": col},
            "properties": [{"id": "unit", "value": "dateTimeAsSystem"}],
        }
        for col in _TIME_COLS
    ]
    overrides += [
        {
            "matcher": {"id": "byName", "options": col},
            "properties": [{"id": "unit", "value": unit}],
        }
        for col, unit in unit_cols.items()
    ]
    return overrides


# ---------------------------------------------------------------------------
# Конструкторы панелей
# ---------------------------------------------------------------------------


def stat(
    title: str,
    sql: str | None = None,
    *,
    prom: str | None = None,
    unit: str = "none",
    decimals: int = 0,
    w: int = 3,
    h: int = 4,
    thresholds: list[dict] | None = None,
) -> dict:
    """Стат / бейдж. Либо CH-SELECT, либо Prometheus-выражение (маленький бейдж)."""
    steps = thresholds or [{"color": "green", "value": None}]
    targets = [target_prom(prom)] if prom else [target_ch(sql or "SELECT 1 AS v")]
    return {
        "datasource": PROM if prom else CH,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": steps},
                "unit": unit,
                "decimals": decimals,
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": 0, "y": 0},
        "options": {
            "colorMode": "value",
            "graphMode": "none",
            "justifyMode": "auto",
            "orientation": "auto",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "textMode": "value",
            "wideLayout": True,
        },
        "targets": targets,
        "title": title,
        "type": "stat",
    }


def ts(title: str, sql: str, unit: str = "none", w: int = 8, h: int = 8) -> dict:
    """Time series."""
    return {
        "datasource": CH,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {
                    "axisCenteredZero": False,
                    "axisColorMode": "text",
                    "axisLabel": "",
                    "axisPlacement": "auto",
                    "barAlignment": 0,
                    "drawStyle": "line",
                    "fillOpacity": 10,
                    "gradientMode": "none",
                    "hideFrom": {"legend": False, "tooltip": False, "viz": False},
                    "lineInterpolation": "linear",
                    "lineWidth": 1,
                    "pointSize": 5,
                    "scaleDistribution": {"type": "linear"},
                    "showPoints": "never",
                    "spanNulls": False,
                    "stacking": {"group": "A", "mode": "none"},
                    "thresholdsStyle": {"mode": "off"},
                },
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": unit,
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": 0, "y": 0},
        "id": 0,
        "options": {
            "legend": {
                "calcs": ["mean", "last"],
                "displayMode": "table",
                "placement": "bottom",
                "showLegend": True,
            },
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [target_ch(sql, fmt=0)],
        "title": title,
        "type": "timeseries",
    }


def bar(title: str, sql: str, unit: str = "none", w: int = 8, h: int = 8) -> dict:
    """Bar chart (горизонтальный)."""
    return {
        "datasource": CH,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "custom": {"fillOpacity": 80, "lineWidth": 1},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": unit,
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": 0, "y": 0},
        "id": 0,
        "options": {
            "orientation": "horizontal",
            "showValue": "auto",
            "xField": "metric",
            "legend": {"displayMode": "list", "placement": "right", "showLegend": False},
            "tooltip": {"mode": "single", "sort": "none"},
            "y": "v",
        },
        "targets": [target_ch(sql, fmt=1)],
        "title": title,
        "type": "barchart",
    }


def pie(title: str, sql: str, w: int = 8, h: int = 8) -> dict:
    return {
        "datasource": CH,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "palette-classic"},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": "none",
            },
            "overrides": [],
        },
        "gridPos": {"h": h, "w": w, "x": 0, "y": 0},
        "id": 0,
        "options": {
            "displayLabels": ["name", "value", "percent"],
            "legend": {"displayMode": "list", "placement": "right", "showLegend": True},
            "pieType": "pie",
            "reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
            "tooltip": {"mode": "single", "sort": "none"},
        },
        "targets": [target_ch(sql, fmt=1)],
        "title": title,
        "type": "piechart",
    }


def table(
    title: str,
    sql: str,
    unit_cols: dict[str, str] | None = None,
    w: int = 24,
    h: int = 8,
    sort_col: str = "timestamp",
) -> dict:
    return {
        "datasource": CH,
        "fieldConfig": {
            "defaults": {
                "color": {"mode": "thresholds"},
                "mappings": [],
                "thresholds": {"mode": "absolute", "steps": [{"color": "green", "value": None}]},
                "unit": "none",
            },
            "overrides": _overrides(unit_cols or {}),
        },
        "gridPos": {"h": h, "w": w, "x": 0, "y": 0},
        "id": 0,
        "options": {
            "cellHeight": "sm",
            "footer": {
                "countRows": False,
                "enablePagination": True,
                "fields": "",
                "reducer": ["sum"],
                "show": False,
            },
            "showHeader": True,
            "sortBy": [{"desc": True, "displayName": sort_col}],
        },
        "targets": [target_ch(sql, fmt=1)],
        "title": title,
        "type": "table",
    }


def var_query(name: str, label: str, sql: str) -> dict:
    """Single-select переменная со значением 'All' в списке опций."""
    return {
        "name": name,
        "type": "query",
        "datasource": CH,
        "definition": sql,
        "query": sql,
        "refresh": 2,
        "includeAll": False,
        "multi": False,
        "allValue": None,
        "hide": 0,
        "label": label,
        "current": {"text": "All", "value": "All", "selected": True},
        # 0 = сохранять порядок строк из SQL ('All' первым), без клиентской сортировки.
        "sort": 0,
    }


def var_sql(column: str, table: str) -> str:
    """Список значений для переменной: 'All' + DISTINCT колонки, 'All' первым."""
    return (
        "SELECT v FROM ("
        f"SELECT 'All' AS v UNION ALL SELECT {column} AS v FROM security_logs.{table} GROUP BY {column}"
        ") ORDER BY (v = 'All') DESC, v"
    )


def layout(rows: list[tuple[str, list[dict]]]) -> list[dict]:
    """Разложить панели по сетке: ряд = панель row + панели справа-налево."""
    out: list[dict] = []
    y = 0
    pid = 1
    for title, panels in rows:
        out.append(
            {
                "collapsed": False,
                "gridPos": {"h": 1, "w": 24, "x": 0, "y": y},
                "id": pid,
                "title": title,
                "type": "row",
            }
        )
        pid += 1
        y += 1
        x = 0
        row_h = 1
        for p in panels:
            w, h = p["gridPos"]["w"], p["gridPos"]["h"]
            if x + w > 24:
                x = 0
                y += row_h
                row_h = 1
            p["gridPos"]["x"] = x
            p["gridPos"]["y"] = y
            p["id"] = pid
            pid += 1
            x += w
            row_h = max(row_h, h)
            out.append(p)
        y += row_h
    return out


def build_dashboard(
    title: str,
    uid: str,
    tags: list[str],
    rows: list[tuple[str, list[dict]]],
    variables: list[dict],
) -> dict:
    return {
        "annotations": {
            "list": [
                {
                    "builtIn": 1,
                    "datasource": {"type": "grafana", "uid": "-- Grafana --"},
                    "enable": True,
                    "hide": True,
                    "iconColor": "rgba(0, 211, 255, 1)",
                    "name": "Annotations & Alerts",
                    "type": "dashboard",
                }
            ]
        },
        "editable": True,
        "fiscalYearStartMonth": 0,
        "graphTooltip": 1,
        "id": None,
        "links": [],
        "panels": layout(rows),
        "refresh": "30s",
        "schemaVersion": 39,
        "tags": tags,
        "templating": {"list": variables},
        "time": {"from": "now-6h", "to": "now"},
        "timepicker": {},
        "timezone": "browser",
        "title": title,
        "uid": uid,
        "version": 1,
        "weekStart": "",
    }


# ---------------------------------------------------------------------------
# Переменные дашбордов
# ---------------------------------------------------------------------------

VARS_1 = [
    var_query("model", "Модель", var_sql("model", "spend_logs_extended")),
    var_query("agent", "Агент (user_id)", var_sql("user_id", "spend_logs_extended")),
    var_query("tool", "Инструмент", var_sql("tool_name", "events_tool_calls")),
    var_query("guardrail", "Гардрейл", var_sql("guardrail_name", "events_guardrails")),
]

VARS_2 = VARS_1 + [
    var_query("severity", "Severity", var_sql("severity", "alert_incidents")),
    var_query("status", "Статус", var_sql("status", "spend_logs_extended")),
]


# ---------------------------------------------------------------------------
# Дашборд 1: «Агент: контроль действий»
# ---------------------------------------------------------------------------


def F(var: str, col: str) -> str:
    """Фильтр по переменной.

    Переменная single-select, в её значениях есть 'All' (см. VARS_*).
    `$ {var:raw}` интерполируется Grafana до отправки запроса:
      - 'All'   → ('All' = 'All') → true → без фильтра;
      - значение → col = '<значение>'.
    """
    return f"AND ('${{{var}:raw}}' = 'All' OR {col} = '${{{var}:raw}}')"


DB1_ROWS: list[tuple[str, list[dict]]] = [
    (
        "Обзор",
        [
            stat(
                "Запросы",
                "SELECT count() AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}",
            ),
            stat(
                "Ошибки, %",
                "SELECT round(100 * countIf(status = 'failure') / count(), 2) AS v"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}",
                unit="percent",
                decimals=2,
            ),
            stat(
                "Стоимость, $",
                "SELECT round(sum(cost), 4) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) AND status = 'success' {F('model', 'model')} {F('agent', 'user_id')}",
                unit="currencyUSD",
                decimals=4,
            ),
            stat(
                "Токены",
                "SELECT sum(total_tokens) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}",
            ),
            stat(
                "TTFT p95, мс",
                "SELECT round(quantile(0.95)(ttft_ms)) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}",
                unit="ms",
            ),
            stat(
                "Вызовы тулов",
                "SELECT count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}",
            ),
            stat(
                "Срабатывания гардрейлов",
                "SELECT count() AS v FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}",
            ),
            stat(
                "Открытые инциденты",
                "SELECT countIf(disposition = 'open') AS v FROM security_logs.alert_incidents",
                thresholds=[{"color": "green", "value": None}, {"color": "red", "value": 1}],
            ),
        ],
    ),
    (
        "Запросы к LLM (spend_logs_extended)",
        [
            ts(
                "Запросы по статусу",
                "SELECT $__timeInterval(timestamp) AS time, status, count() AS v"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}"
                " GROUP BY time, status ORDER BY time",
                w=12,
            ),
            ts(
                "Стоимость по времени, $",
                "SELECT $__timeInterval(timestamp) AS time, sum(cost) AS v"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) AND status = 'success' {F('model', 'model')} {F('agent', 'user_id')}"
                " GROUP BY time ORDER BY time",
                unit="currencyUSD",
                w=6,
            ),
            ts(
                "TTFT p95, мс",
                "SELECT $__timeInterval(timestamp) AS time, quantile(0.95)(ttft_ms) AS v"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}"
                " GROUP BY time ORDER BY time",
                unit="ms",
                w=6,
            ),
            ts(
                "Токены: prompt/completion",
                "SELECT $__timeInterval(timestamp) AS time, 'prompt' AS series,"
                " sum(prompt_tokens) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}"
                " GROUP BY time, series ORDER BY time"
                " UNION ALL"
                " SELECT $__timeInterval(timestamp) AS time, 'completion' AS series,"
                " sum(completion_tokens) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}"
                " GROUP BY time, series ORDER BY time",
                w=12,
            ),
            bar(
                "Запросы по модели",
                "SELECT model AS metric, count() AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')}"
                " GROUP BY model ORDER BY v DESC",
                w=6,
            ),
            bar(
                "Ошибки по модели",
                "SELECT model AS metric, count() AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) AND status = 'failure' {F('agent', 'user_id')}"
                " GROUP BY model ORDER BY v DESC",
                w=6,
            ),
            table(
                "Последние запросы",
                "SELECT timestamp, request_id, trace_id, model, user_id, status, cost,"
                " prompt_tokens, completion_tokens, total_tokens, ttft_ms,"
                " tool_calls_count, guardrails_count, requester_ip, user_agent, error_str"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')}"
                " ORDER BY timestamp DESC LIMIT 100",
                unit_cols={"cost": "currencyUSD", "ttft_ms": "ms"},
            ),
        ],
    ),
    (
        "Инструменты (events_tool_calls)",
        [
            ts(
                "Вызовы тулов по времени",
                "SELECT $__timeInterval(timestamp) AS time, count() AS v"
                " FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}"
                " GROUP BY time ORDER BY time",
                w=12,
            ),
            bar(
                "Top-10 тулов",
                "SELECT tool_name AS metric, count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')}"
                " GROUP BY tool_name ORDER BY v DESC LIMIT 10",
                w=6,
            ),
            bar(
                "По агентам (user_id)",
                "SELECT user_id AS metric, count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('tool', 'tool_name')}"
                " GROUP BY user_id ORDER BY v DESC LIMIT 10",
                w=6,
            ),
            table(
                "Последние вызовы тулов",
                "SELECT timestamp, request_id, model, user_id, tool_name, status,"
                " substring(arguments, 1, 400) AS arguments"
                " FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}"
                " ORDER BY timestamp DESC LIMIT 100",
            ),
        ],
    ),
    (
        "Гардрейлы (events_guardrails)",
        [
            ts(
                "Срабатывания по action",
                "SELECT $__timeInterval(timestamp) AS time, action, count() AS v"
                " FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " GROUP BY time, action ORDER BY time",
                w=12,
            ),
            bar(
                "Top-10 гардрейлов",
                "SELECT guardrail_name AS metric, count() AS v"
                " FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')}"
                " GROUP BY guardrail_name ORDER BY v DESC LIMIT 10",
                w=6,
            ),
            pie(
                "Типы сущностей",
                "SELECT entity_type AS metric, count() AS v"
                " FROM security_logs.events_guardrails"
                " ARRAY JOIN entity_types AS entity_type"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " GROUP BY entity_type ORDER BY v DESC LIMIT 10",
                w=6,
            ),
            table(
                "Последние срабатывания",
                "SELECT timestamp, request_id, model, user_id, guardrail_name,"
                " guardrail_mode, action, duration_ms,"
                " arrayStringConcat(entity_types, ',') AS entity_types,"
                " masked_entity_counts, status"
                " FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " ORDER BY timestamp DESC LIMIT 100",
                unit_cols={"duration_ms": "ms"},
            ),
        ],
    ),
    (
        "Инциденты (alert_incidents)",
        [
            ts(
                "Инциденты по severity",
                "SELECT $__timeInterval(triggered_at) AS time, severity, count() AS v"
                " FROM security_logs.alert_incidents"
                " WHERE $__timeFilter(triggered_at)"
                " GROUP BY time, severity ORDER BY time",
                w=12,
            ),
            bar(
                "Инциденты по правилам",
                "SELECT rule_name AS metric, count() AS v"
                " FROM security_logs.alert_incidents"
                " WHERE $__timeFilter(triggered_at)"
                " GROUP BY rule_name ORDER BY v DESC LIMIT 10",
                w=12,
            ),
            table(
                "Последние инциденты",
                "SELECT triggered_at, rule_name, severity, triggered_value,"
                " disposition, context"
                " FROM security_logs.alert_incidents"
                " WHERE $__timeFilter(triggered_at)"
                " ORDER BY triggered_at DESC LIMIT 100",
                sort_col="triggered_at",
            ),
        ],
    ),
    (
        "Метрики агента (Prometheus)",
        [
            stat("Запуски Observer", prom="sum(agent_observer_runs_total)"),
            stat("Инциденты (всего)", prom="sum(agent_correlator_incidents_total)"),
            stat("FP-доля", prom="sum(agent_incidents_fp_ratio)", decimals=2),
            stat("Активы (created)", prom="sum(agent_observer_assets_created_total)"),
            stat("MCP-тулы (created)", prom="sum(agent_observer_mcp_tools_created_total)"),
            stat("Правила (promoted)", prom="sum(agent_promoted_rules_total)"),
            stat("Активы (promoted)", prom="sum(agent_promoted_assets_total)"),
            stat("Вызовы без декларации", prom="sum(agent_tools_without_declaration_total)"),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Дашборд 2: «Сырые данные из view»
# ---------------------------------------------------------------------------

DB2_ROWS: list[tuple[str, list[dict]]] = [
    (
        "Запросы (spend_logs_extended)",
        [
            stat(
                "Запросов",
                "SELECT count() AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                w=4,
            ),
            stat(
                "Ошибки, %",
                "SELECT round(100 * countIf(status = 'failure') / count(), 2) AS v"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                unit="percent",
                decimals=2,
                w=4,
            ),
            stat(
                "Стоимость, $",
                "SELECT round(sum(cost), 4) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) AND status = 'success' {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                unit="currencyUSD",
                decimals=4,
                w=4,
            ),
            stat(
                "Токены",
                "SELECT sum(total_tokens) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                w=4,
            ),
            stat(
                "Tool calls",
                "SELECT sum(tool_calls_count) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                w=4,
            ),
            stat(
                "Guardrails",
                "SELECT sum(guardrails_count) AS v FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}",
                w=4,
            ),
            table(
                "Сырые строки",
                "SELECT timestamp, request_id, trace_id, user_id, model, model_group,"
                " custom_llm_provider, status, cost, prompt_tokens, completion_tokens,"
                " total_tokens, ttft_ms, tool_calls_count, guardrails_count,"
                " requester_ip, user_agent, error_str"
                " FROM security_logs.spend_logs_extended"
                f" WHERE $__timeFilter(timestamp) {F('model', 'model')} {F('agent', 'user_id')} {F('status', 'status')}"
                " ORDER BY timestamp DESC LIMIT 500",
                unit_cols={"cost": "currencyUSD", "ttft_ms": "ms"},
                h=10,
            ),
        ],
    ),
    (
        "Tool calls (events_tool_calls)",
        [
            stat(
                "Вызовов",
                "SELECT count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}",
                w=4,
            ),
            stat(
                "Уникальных запросов",
                "SELECT uniq(request_id) AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}",
                w=4,
            ),
            bar(
                "Top-10 тулов",
                "SELECT tool_name AS metric, count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')}"
                " GROUP BY tool_name ORDER BY v DESC LIMIT 10",
                w=8,
            ),
            bar(
                "По статусу",
                "SELECT status AS metric, count() AS v FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}"
                " GROUP BY status ORDER BY v DESC",
                w=8,
            ),
            table(
                "Сырые вызовы",
                "SELECT timestamp, request_id, model, user_id, tool_name, status,"
                " substring(arguments, 1, 1000) AS arguments"
                " FROM security_logs.events_tool_calls"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('tool', 'tool_name')}"
                " ORDER BY timestamp DESC LIMIT 500",
                h=10,
            ),
        ],
    ),
    (
        "Guardrails (events_guardrails)",
        [
            stat(
                "Срабатываний",
                "SELECT count() AS v FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}",
                w=4,
            ),
            stat(
                "PII-сущностей (всего)",
                "SELECT count() AS v FROM security_logs.events_guardrails"
                " ARRAY JOIN entity_types AS et"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " AND length(entity_types) > 0",
                w=4,
            ),
            pie(
                "Типы сущностей",
                "SELECT entity_type AS metric, count() AS v"
                " FROM security_logs.events_guardrails"
                " ARRAY JOIN entity_types AS entity_type"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " GROUP BY entity_type ORDER BY v DESC LIMIT 10",
                w=8,
            ),
            bar(
                "По action/status",
                "SELECT concat(action, '/', status) AS metric, count() AS v"
                " FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " GROUP BY metric ORDER BY v DESC",
                w=8,
            ),
            table(
                "Сырые срабатывания",
                "SELECT timestamp, request_id, model, user_id, guardrail_name,"
                " guardrail_provider, guardrail_mode, action, status, duration_ms,"
                " entity_types, masked_entity_counts"
                " FROM security_logs.events_guardrails"
                f" WHERE $__timeFilter(timestamp) {F('agent', 'user_id')} {F('guardrail', 'guardrail_name')}"
                " ORDER BY timestamp DESC LIMIT 500",
                unit_cols={"duration_ms": "ms"},
                h=10,
            ),
        ],
    ),
    (
        "Инциденты (alert_incidents)",
        [
            stat(
                "Всего",
                "SELECT count() AS v FROM security_logs.alert_incidents"
                f" WHERE $__timeFilter(triggered_at) {F('severity', 'severity')}",
                w=4,
            ),
            stat(
                "Открытых",
                "SELECT countIf(disposition = 'open') AS v FROM security_logs.alert_incidents"
                f" WHERE $__timeFilter(triggered_at) {F('severity', 'severity')}",
                w=4,
            ),
            bar(
                "По правилам",
                "SELECT rule_name AS metric, count() AS v FROM security_logs.alert_incidents"
                f" WHERE $__timeFilter(triggered_at) {F('severity', 'severity')}"
                " GROUP BY rule_name ORDER BY v DESC LIMIT 10",
                w=8,
            ),
            bar(
                "По severity",
                "SELECT severity AS metric, count() AS v FROM security_logs.alert_incidents"
                " WHERE $__timeFilter(triggered_at)"
                " GROUP BY severity ORDER BY v DESC",
                w=8,
            ),
            table(
                "Сырые инциденты",
                "SELECT triggered_at, rule_name, severity, triggered_value, disposition, context"
                " FROM security_logs.alert_incidents"
                f" WHERE $__timeFilter(triggered_at) {F('severity', 'severity')}"
                " ORDER BY triggered_at DESC LIMIT 500",
                sort_col="triggered_at",
                h=10,
            ),
        ],
    ),
    (
        "Инвентарь и предложения",
        [
            table(
                "Активы (assets)",
                "SELECT asset_key, asset_type, asset_subtype, display_name, owner,"
                " criticality, source_of_truth, is_active, first_seen, last_seen,"
                " observation_count"
                " FROM security_logs.assets FINAL"
                " ORDER BY last_seen DESC LIMIT 200",
                sort_col="last_seen",
            ),
            table(
                "Предложения активов (asset_proposals)",
                "SELECT created_at, action, asset_key, confidence, status, rationale"
                " FROM security_logs.asset_proposals FINAL"
                " ORDER BY created_at DESC LIMIT 200",
                sort_col="created_at",
            ),
            table(
                "Предложения правил (rule_proposals)",
                "SELECT created_at, status, hit_rate_sample, estimated_cost, rationale,"
                " reviewed_by"
                " FROM security_logs.rule_proposals FINAL"
                " ORDER BY created_at DESC LIMIT 200",
                unit_cols={"estimated_cost": "currencyUSD"},
                sort_col="created_at",
            ),
            table(
                "Правила (alert_rules)",
                "SELECT rule_name, severity, rule_kind, check_interval, is_active,"
                " created_by, created_at, last_evaluated, last_hit"
                " FROM security_logs.alert_rules"
                " ORDER BY created_at DESC LIMIT 200",
                sort_col="created_at",
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Сборка и запись
# ---------------------------------------------------------------------------


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dashboards = [
        build_dashboard(
            "Агент: контроль действий",
            "agent-activity-control",
            ["appsecgate", "agent"],
            DB1_ROWS,
            VARS_1,
        ),
        build_dashboard(
            "Сырые данные из view",
            "raw-views-explorer",
            ["appsecgate", "explorer"],
            DB2_ROWS,
            VARS_2,
        ),
    ]
    for db in dashboards:
        path = OUT_DIR / f"{db['uid']}.json"
        path.write_text(json.dumps(db, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {path.name} — {len(db['panels'])} panels")


if __name__ == "__main__":
    main()
