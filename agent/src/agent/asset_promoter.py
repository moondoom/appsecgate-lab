"""Asset auto-promoter: moves ``asset_proposals`` into ``assets``.

ClickHouse rights do not let the agent write into ``assets`` directly
(only ``vector``/``otel`` write there) — the Observer creates ``asset_proposals``,
and this module moves them into the inventory through a dedicated narrow user
``agent_asset_promoter`` (INSERT only on ``assets``).

Hybrid approval mode:
* ``status='approved'``                     — manual approval, always promoted;
* ``status='draft'`` + ``confidence >= threshold`` — autopilot (Observer sets 0.9);
* everything else                           — waits for a manual ``approved``.

The move is an INSERT into ``assets``: ``ReplacingMergeTree(updated_at)`` keyed by
``(asset_type, asset_key)`` collapses duplicates and updates ``last_seen`` /
``observation_count``. The proposal is then marked ``promoted`` via a new
row version (same mechanics as rule promotion).
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
    """Select proposals ready to be promoted (pure function, for tests).

    Criterion: ``action='create'`` and (``status='approved'`` or
    ``status='draft'`` with ``confidence >= threshold``).
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
    """Build a row for INSERT into assets; existing — the current inventory record."""
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
    """New proposal version with status='promoted' (ReplacingMergeTree replaces the old one)."""
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
    """Run one asset auto-promoter pass.

    Returns counters: ``candidates`` (selected), ``promoted`` (moved).
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
