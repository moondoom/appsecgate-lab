"""Correlator: runs active periodic rules and writes incidents.

Reads ``alert_rules`` (reader), executes the ``query`` of each active periodic
rule, and turns every result row into an ``alert_incidents`` entry (promoter).
Severity, triggered_value and context come from the result row (as in static
rules — ``'high' AS severity``).
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from clickhouse_connect.driver import Client

from agent.metrics import correlator_incidents

logger = logging.getLogger(__name__)

_INCIDENT_COLUMNS = ["rule_id", "rule_name", "triggered_value", "severity", "context"]


def _fetch_rules(reader: Client) -> list[dict[str, Any]]:
    query = """
        SELECT rule_id, rule_name, query, severity, check_interval
        FROM security_logs.alert_rules
        WHERE is_active = 1 AND rule_kind = 'periodic'
    """
    return list(reader.query(query).named_results())


def _rows_to_incidents(
    rule: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> list[tuple[str, str, float, str, str]]:
    """Map rule result rows to alert_incidents fields."""
    incidents: list[tuple[str, str, float, str, str]] = []
    for row in rows:
        severity = str(row.get("severity") or rule["severity"] or "medium")
        triggered_value = float(row.get("triggered_value") or 1)
        context = str(row.get("context") or "{}")
        incidents.append(
            (str(rule["rule_id"]), str(rule["rule_name"]), triggered_value, severity, context)
        )
    return incidents


def run_once(reader: Client, promoter: Client, max_incidents: int = 100) -> dict[str, int]:
    """Run one Correlator pass. Returns ``rules``/``incidents`` counters."""
    rules = _fetch_rules(reader)
    if not rules:
        logger.info("correlator: no active periodic rules")
        return {"rules": 0, "incidents": 0}

    total_incidents = 0
    for rule in rules:
        try:
            result = reader.query(str(rule["query"]))
        except Exception as exc:  # noqa: BLE001 — a bad rule must not break the whole loop
            logger.warning("correlator: rule %s failed: %s", rule["rule_name"], exc)
            continue

        rows = list(result.named_results())
        if not rows:
            continue

        incidents = _rows_to_incidents(rule, rows)
        if not incidents:
            continue

        promoter.insert("security_logs.alert_incidents", incidents, column_names=_INCIDENT_COLUMNS)
        for inc in incidents:
            correlator_incidents.labels(inc[3]).inc()
        total_incidents += len(incidents)
        logger.info("correlator: rule %s -> %d incident(s)", rule["rule_name"], len(incidents))

        if total_incidents >= max_incidents:
            break

    return {"rules": len(rules), "incidents": total_incidents}
