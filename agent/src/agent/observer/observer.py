"""Observer: превращает наблюдения (spend_logs) в предложения по активам.

Права пользователей ClickHouse не позволяют агенту писать в ``assets``
(туда пишут только ``vector``/``otel``), поэтому Observer формирует
``asset_proposals`` (action='create') через ``agent_writer``.

Источник сейчас — ``litellm.spend_logs`` (LiteLLM сама пишет туда spend).
Из каждой записи извлекаются наблюдаемые активы:

* ``external_api`` — по ``api_base``;
* ``ai_agent``     — по ``user`` (кто ходит через прокси);
* ``user``         — по ``end_user``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from clickhouse_connect.driver import Client

from agent.metrics import observer_assets_created, observer_runs
from agent.observer.normalize import make_asset_key

# Окно наблюдения по умолчанию: смотрим spend за последние 30 минут.
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
    """Извлечь уникальных кандидатов-активов из строк spend_logs."""
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
                    attributes={"observed_in": "litellm.spend_logs"},
                ),
            )
        user = str(row.get("user") or "").strip()
        if user:
            key = make_asset_key("ai_agent", user)
            candidates.setdefault(
                key,
                AssetCandidate(
                    asset_type="ai_agent",
                    asset_key=key,
                    display_name=user,
                    attributes={"observed_in": "litellm.spend_logs"},
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
                    attributes={"observed_in": "litellm.spend_logs"},
                ),
            )
    return list(candidates.values())


def _fetch_recent_spend(reader: Client, since_minutes: int) -> list[dict[str, Any]]:
    """Прочитать свежие записи spend_logs."""
    query = f"""
        SELECT start_time, user, end_user, api_base, model, status
        FROM litellm.spend_logs
        WHERE start_time >= now() - INTERVAL {int(since_minutes)} MINUTE
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
            f"Observed in litellm.spend_logs as {c.asset_type}",
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

    rows = _fetch_recent_spend(reader, since_minutes)
    candidates = extract_candidates(rows)
    new = _filter_new(reader, candidates)
    _write_proposals(writer, new)

    observer_assets_created.inc(len(new))
    return {"spend_rows": len(rows), "candidates": len(candidates), "new_proposals": len(new)}
