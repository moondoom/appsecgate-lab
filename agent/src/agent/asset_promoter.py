"""Авто-промоутер активов: перенос ``asset_proposals`` в ``assets``.

Права ClickHouse не позволяют агенту писать в ``assets`` напрямую
(туда пишут только ``vector``/``otel``) — Observer создаёт ``asset_proposals``,
а этот модуль переносит их в инвентарь через отдельного узкого пользователя
``agent_asset_promoter`` (INSERT только на ``assets``).

Гибридный режим одобрения:
* ``status='approved'``                     — ручное одобрение, переносится всегда;
* ``status='draft'`` + ``confidence >= порог`` — автопилот (Observer ставит 0.9);
* остальное                                 — ждёт ручного ``approved``.

Перенос — это INSERT в ``assets``: ``ReplacingMergeTree(updated_at)`` по ключу
``(asset_type, asset_key)`` сам схлопывает дубли и обновляет ``last_seen`` /
``observation_count``. Затем proposal помечается ``promoted`` новой версией
строки (та же механика, что в promote правил).
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from clickhouse_connect.driver import Client

from agent.metrics import promoted_assets

DEFAULT_THRESHOLD = 0.9


def filter_eligible(
    rows: Sequence[Mapping[str, Any]],
    threshold: float = DEFAULT_THRESHOLD,
) -> list[dict[str, Any]]:
    """Отобрать proposals, готовые к переносу (чистая функция, для тестов).

    Критерий: ``action='create'`` и (``status='approved'`` либо
    ``status='draft'`` с ``confidence >= threshold``).
    """
    eligible: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("action") or "") != "create":
            continue
        status = str(row.get("status") or "")
        try:
            confidence = float(row.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        if status == "approved" or (status == "draft" and confidence >= threshold):
            eligible.append(dict(row))
    return eligible


def _build_asset_row(
    proposal: Mapping[str, Any],
    existing: Mapping[str, Any] | None,
) -> tuple[Any, ...]:
    """Собрать строку для INSERT в assets; existing — текущая запись инвентаря."""
    try:
        data = json.loads(str(proposal.get("proposed_data") or "{}"))
    except ValueError:
        data = {}
    asset_type = str(data.get("asset_type") or "unknown")
    display_name = str(data.get("display_name") or proposal["asset_key"])
    attributes = json.dumps(data.get("attributes", {}), ensure_ascii=False)

    now = datetime.now(UTC)
    if existing is not None:
        first_seen = existing["first_seen"]
        observation_count = int(existing["observation_count"]) + 1
    else:
        first_seen = now
        observation_count = 1

    return (
        proposal["asset_key"],
        asset_type,
        display_name,
        "",
        "unknown",
        attributes,
        first_seen,
        now,
        observation_count,
        "observed",
        1,
        now,
    )


def _build_proposal_row(
    proposal: Mapping[str, Any],
    now: datetime,
) -> tuple[Any, ...]:
    """Новая версия proposal со status='promoted' (ReplacingMergeTree заменит старую)."""
    return (
        proposal["proposal_id"],
        proposal["action"],
        proposal["asset_key"],
        str(proposal.get("proposed_data") or "{}"),
        str(proposal.get("rationale") or ""),
        float(proposal.get("confidence") or 0.0),
        "promoted",
        proposal["created_at"],
        now,
        now,
    )


def promote_once(
    reader: Client,
    writer: Client,
    promoter: Client,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, int]:
    """Один проход авто-промоутера активов.

    Возвращает счётчики: ``candidates`` (отобрано), ``promoted`` (перенесено).
    """
    rows = list(
        reader.query(
            "SELECT proposal_id, action, asset_key, proposed_data, rationale, "
            "confidence, status, created_at "
            "FROM security_logs.asset_proposals FINAL "
            "WHERE action = 'create' "
            "AND (status = 'approved' "
            "     OR (status = 'draft' AND confidence >= {thr:Float64}))",
            parameters={"thr": threshold},
        ).named_results()
    )
    eligible = filter_eligible(rows, threshold)
    if not eligible:
        return {"candidates": 0, "promoted": 0}

    keys = [str(p["asset_key"]) for p in eligible]
    existing: dict[str, Mapping[str, Any]] = {}
    for row in reader.query(
        "SELECT asset_key, first_seen, observation_count "
        "FROM security_logs.assets FINAL WHERE asset_key IN {keys:Array(String)}",
        parameters={"keys": keys},
    ).named_results():
        existing[str(row["asset_key"])] = row

    now = datetime.now(UTC)
    asset_rows = [_build_asset_row(p, existing.get(str(p["asset_key"]))) for p in eligible]
    proposal_rows = [_build_proposal_row(p, now) for p in eligible]

    promoter.insert(
        "security_logs.assets",
        asset_rows,
        column_names=[
            "asset_key",
            "asset_type",
            "display_name",
            "owner",
            "criticality",
            "attributes",
            "first_seen",
            "last_seen",
            "observation_count",
            "source_of_truth",
            "is_active",
            "updated_at",
        ],
    )
    writer.insert(
        "security_logs.asset_proposals",
        proposal_rows,
        column_names=[
            "proposal_id",
            "action",
            "asset_key",
            "proposed_data",
            "rationale",
            "confidence",
            "status",
            "created_at",
            "updated_at",
            "reviewed_at",
        ],
    )
    promoted_assets.inc(len(eligible))
    return {"candidates": len(eligible), "promoted": len(eligible)}
