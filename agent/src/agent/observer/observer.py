"""Observer: превращает наблюдения (витрины security_logs) в предложения по активам.

Права пользователей ClickHouse не позволяют агенту писать в ``assets``
(туда пишут только ``vector``/``otel``), поэтому Observer формирует
``asset_proposals`` (action='create') через ``agent_writer``.

Источники — производные витрины из ``litellm.spend_logs``
(см. clickhouse/init/08_derived_views.sql):

* ``security_logs.spend_logs_extended`` — 1:1 со spend_logs + вычисляемые поля;
* ``security_logs.events_tool_calls``   — одна строка на вызов инструмента;
* ``security_logs.events_guardrails``   — одна строка на срабатывание гардрейла.

Из наблюдений извлекаются активы-кандидаты:

* ``external_api`` — по ``api_base``;
* ``ai_agent``     — по ``user_id`` (кто ходит через прокси);
* ``user``         — по ``end_user``;
* ``tool``         — по ``tool_name`` из events_tool_calls;
* ``guardrail``    — по ``guardrail_name`` из events_guardrails.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from clickhouse_connect.driver import Client

from agent.metrics import (
    observer_assets_created,
    observer_mcp_tools_created,
    observer_runs,
)
from agent.observer.normalize import make_asset_key

# Окно наблюдения по умолчанию: смотрим витрины за последние 30 минут.
DEFAULT_SINCE_MINUTES = 30

_CONFIDENCE_CREATE = 0.9


@dataclass(frozen=True)
class AssetCandidate:
    """Наблюдаемый актив-кандидат для предложения."""

    asset_type: str
    asset_key: str
    display_name: str
    attributes: dict[str, Any] = field(default_factory=dict)


def _normalize_api_base(api_base: str) -> str:
    """Нормализовать api_base для ключа актива."""
    return api_base.rstrip("/").lower()


def extract_candidates(rows: Sequence[Mapping[str, Any]]) -> list[AssetCandidate]:
    """Извлечь уникальных кандидатов-активов из строк spend_logs_extended."""
    candidates: dict[str, AssetCandidate] = {}
    for row in rows:
        api_base = str(row.get("api_base") or "").strip()
        if api_base:
            key = make_asset_key("external_api", _normalize_api_base(api_base))
            candidates.setdefault(
                key,
                AssetCandidate(
                    asset_type="external_api",
                    asset_key=key,
                    display_name=api_base,
                    attributes={
                        "observed_in": "security_logs.spend_logs_extended",
                        "model": str(row.get("model") or ""),
                        "model_group": str(row.get("model_group") or ""),
                        "custom_llm_provider": str(row.get("custom_llm_provider") or ""),
                    },
                ),
            )
        user_id = str(row.get("user_id") or "").strip()
        if user_id:
            key = make_asset_key("ai_agent", user_id)
            candidates.setdefault(
                key,
                AssetCandidate(
                    asset_type="ai_agent",
                    asset_key=key,
                    display_name=user_id,
                    attributes={
                        "observed_in": "security_logs.spend_logs_extended",
                        "requester_ip": str(row.get("requester_ip") or ""),
                        "user_agent": str(row.get("user_agent") or ""),
                        "tool_calls_count": row.get("tool_calls_count") or 0,
                        "guardrails_count": row.get("guardrails_count") or 0,
                    },
                ),
            )
        end_user = str(row.get("end_user") or "").strip()
        if end_user:
            key = make_asset_key("user", end_user)
            candidates.setdefault(
                key,
                AssetCandidate(
                    asset_type="user",
                    asset_key=key,
                    display_name=end_user,
                    attributes={
                        "observed_in": "security_logs.spend_logs_extended",
                        "requester_ip": str(row.get("requester_ip") or ""),
                        "user_agent": str(row.get("user_agent") or ""),
                    },
                ),
            )
    return list(candidates.values())


def extract_tool_candidates(rows: Sequence[Mapping[str, Any]]) -> list[AssetCandidate]:
    """Извлечь кандидатов типа ``tool`` из сгруппированных строк events_tool_calls."""
    candidates: dict[str, AssetCandidate] = {}
    for row in rows:
        tool_name = str(row.get("tool_name") or "").strip()
        if not tool_name:
            continue
        key = make_asset_key("tool", tool_name)
        candidates.setdefault(
            key,
            AssetCandidate(
                asset_type="tool",
                asset_key=key,
                display_name=tool_name,
                attributes={
                    "observed_in": "security_logs.events_tool_calls",
                    "user_id": str(row.get("user_id") or ""),
                    "model": str(row.get("model") or ""),
                    "calls": int(row.get("calls") or 0),
                },
            ),
        )
    return list(candidates.values())


def extract_guardrail_candidates(rows: Sequence[Mapping[str, Any]]) -> list[AssetCandidate]:
    """Извлечь кандидатов типа ``guardrail`` из строк events_guardrails."""
    candidates: dict[str, AssetCandidate] = {}
    for row in rows:
        guardrail_name = str(row.get("guardrail_name") or "").strip()
        if not guardrail_name:
            continue
        key = make_asset_key("guardrail", guardrail_name)
        candidates.setdefault(
            key,
            AssetCandidate(
                asset_type="guardrail",
                asset_key=key,
                display_name=guardrail_name,
                attributes={
                    "observed_in": "security_logs.events_guardrails",
                    "provider": str(row.get("guardrail_provider") or ""),
                    "mode": str(row.get("guardrail_mode") or ""),
                    "action": str(row.get("action") or ""),
                    "firings": int(row.get("firings") or 0),
                },
            ),
        )
    return list(candidates.values())


def _fetch_recent_rows(reader: Client, since_minutes: int) -> list[dict[str, Any]]:
    """Прочитать свежие строки spend_logs_extended (витрина 1:1 со spend_logs)."""
    query = f"""
        SELECT timestamp, user_id, end_user, api_base, model, model_group,
               custom_llm_provider, tool_calls_count, guardrails_count,
               requester_ip, user_agent
        FROM security_logs.spend_logs_extended
        WHERE timestamp >= now() - INTERVAL {int(since_minutes)} MINUTE
    """
    result = reader.query(query)
    return list(result.named_results())


def _fetch_recent_tools(reader: Client, since_minutes: int) -> list[dict[str, Any]]:
    """Сгруппировать вызовы инструментов из events_tool_calls за окно."""
    query = f"""
        SELECT tool_name, user_id, model, uniq(request_id) AS calls
        FROM security_logs.events_tool_calls
        WHERE timestamp >= now() - INTERVAL {int(since_minutes)} MINUTE
        GROUP BY tool_name, user_id, model
    """
    result = reader.query(query)
    return list(result.named_results())


def _fetch_recent_guardrails(reader: Client, since_minutes: int) -> list[dict[str, Any]]:
    """Сгруппировать срабатывания гардрейлов из events_guardrails за окно."""
    query = f"""
        SELECT guardrail_name, guardrail_provider, guardrail_mode, action,
               uniq(request_id) AS firings
        FROM security_logs.events_guardrails
        WHERE timestamp >= now() - INTERVAL {int(since_minutes)} MINUTE
        GROUP BY guardrail_name, guardrail_provider, guardrail_mode, action
    """
    result = reader.query(query)
    return list(result.named_results())


def _filter_new(reader: Client, candidates: Sequence[AssetCandidate]) -> list[AssetCandidate]:
    """Оставить только кандидатов, которых нет ни в assets, ни в asset_proposals."""
    keys = [c.asset_key for c in candidates]
    if not keys:
        return []

    existing: set[str] = set()
    for table in ("security_logs.assets", "security_logs.asset_proposals"):
        query = f"SELECT asset_key FROM {table} FINAL WHERE asset_key IN {{keys:Array(String)}}"
        for row in reader.query(query, parameters={"keys": keys}).named_results():
            existing.add(str(row["asset_key"]))

    return [c for c in candidates if c.asset_key not in existing]


def _write_proposals(writer: Client, candidates: Sequence[AssetCandidate]) -> None:
    """Записать asset_proposals (action='create')."""
    if not candidates:
        return
    rows = [
        (
            "create",
            c.asset_key,
            json.dumps(
                {
                    "asset_type": c.asset_type,
                    "display_name": c.display_name,
                    "attributes": c.attributes,
                },
                ensure_ascii=False,
            ),
            f"Observed in {c.attributes.get('observed_in', 'security_logs')} as {c.asset_type}",
            _CONFIDENCE_CREATE,
        )
        for c in candidates
    ]
    writer.insert(
        "security_logs.asset_proposals",
        rows,
        column_names=["action", "asset_key", "proposed_data", "rationale", "confidence"],
    )


def run_once(
    reader: Client,
    writer: Client,
    since_minutes: int = DEFAULT_SINCE_MINUTES,
) -> dict[str, int]:
    """Один проход Observer.

    Возвращает счётчики: ``spend_rows``, ``candidates``, ``new_proposals``.
    """
    observer_runs.inc()

    rows = _fetch_recent_rows(reader, since_minutes)
    candidates = extract_candidates(rows)
    candidates += extract_tool_candidates(_fetch_recent_tools(reader, since_minutes))
    candidates += extract_guardrail_candidates(_fetch_recent_guardrails(reader, since_minutes))

    new = _filter_new(reader, candidates)
    _write_proposals(writer, new)

    tools_new = sum(1 for c in new if c.asset_type == "tool")
    observer_assets_created.inc(len(new))
    observer_mcp_tools_created.inc(tools_new)
    return {"spend_rows": len(rows), "candidates": len(candidates), "new_proposals": len(new)}
