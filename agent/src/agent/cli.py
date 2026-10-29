"""CLI для агента аудита.

Подкоманды:

* ``load-rules DIR``  — загрузить статические правила из ``DIR/*.sql`` в ``alert_rules``;
* ``observe``         — один проход Observer (витрины security_logs -> asset_proposals);
* ``correlate``       — один проход Correlator (правила -> alert_incidents);
* ``propose``         — Rule-Engine: сгенерировать rule_proposals через хост-LiteLLM;
* ``promote ID``      — промоутить approved rule_proposal в alert_rules;
* ``serve``           — запустить планировщик (APScheduler) со всеми модулями.
"""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from agent.config import settings
from agent.db import get_asset_promoter, get_promoter, get_reader, get_writer
from agent.metrics import active_rules, validator_rejections
from agent.validator import extract_severity, validate_sql

logger = logging.getLogger(__name__)


def _setup_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _rule_name_from_file(path: Path) -> str:
    """Имя правила — из первой строки-комментария файла, иначе имя файла."""
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            name = stripped[2:].strip()
            if name:
                return name
    return path.stem


def cmd_load_rules(args: argparse.Namespace) -> int:
    """Загрузить статические правила из rules/static в alert_rules."""
    rules_dir = Path(args.dir)
    files = sorted(rules_dir.glob("*.sql"))
    if not files:
        logger.error("no .sql files in %s", rules_dir)
        return 1

    reader, promoter = get_reader(), get_promoter()

    # Идемпотентность: не перезагружаем уже существующие имена правил.
    names = [_rule_name_from_file(f) for f in files]
    existing: set[str] = set()
    if names:
        for row in reader.query(
            "SELECT rule_name FROM security_logs.alert_rules "
            "WHERE rule_name IN {names:Array(String)}",
            parameters={"names": names},
        ).named_results():
            existing.add(str(row["rule_name"]))

    loaded, skipped, rejected = 0, 0, 0
    for path, name in zip(files, names, strict=True):
        if name in existing:
            logger.info("load-rules: %s already loaded, skip", name)
            skipped += 1
            continue

        query = path.read_text(encoding="utf-8")
        ok, reason = validate_sql(query)
        if not ok:
            validator_rejections.labels(reason).inc()
            logger.error("load-rules: %s rejected (%s)", name, reason)
            rejected += 1
            continue

        severity = extract_severity(query)
        promoter.insert(
            "security_logs.alert_rules",
            [(name, query, severity, "periodic", 60, 1, "human", datetime.now(UTC))],
            column_names=[
                "rule_name",
                "query",
                "severity",
                "rule_kind",
                "check_interval",
                "is_active",
                "created_by",
                "last_evaluated",
            ],
        )
        active_rules.labels(severity).inc()
        loaded += 1
        logger.info("load-rules: loaded %s (severity=%s)", name, severity)

    print(f"load-rules: loaded={loaded} skipped={skipped} rejected={rejected}")
    return 0 if rejected == 0 else 2


def cmd_observe(_args: argparse.Namespace) -> int:
    """Один проход Observer."""
    from agent.observer.observer import run_once

    stats = run_once(get_reader(), get_writer())
    print(f"observe: {stats}")
    return 0


def cmd_correlate(_args: argparse.Namespace) -> int:
    """Один проход Correlator."""
    from agent.correlator import run_once

    stats = run_once(get_reader(), get_promoter())
    print(f"correlate: {stats}")
    return 0


def cmd_propose(_args: argparse.Namespace) -> int:
    """Rule-Engine: предложить правила через хост-LiteLLM."""
    from agent.rule_engine import run_once

    stats = run_once(get_reader(), get_writer())
    if stats.get("error"):
        print(f"propose: error: {stats['error']}", file=sys.stderr)
        return 1
    print(f"propose: {stats}")
    return 0


def cmd_promote(args: argparse.Namespace) -> int:
    """Промоутить approved rule_proposal в alert_rules."""
    reader, writer, promoter = get_reader(), get_writer(), get_promoter()

    proposal = next(
        iter(
            reader.query(
                "SELECT proposal_id, proposed_query, rationale, status, created_at "
                "FROM security_logs.rule_proposals FINAL WHERE proposal_id = {pid:UUID}",
                parameters={"pid": args.rule_id},
            ).named_results()
        ),
        None,
    )
    if proposal is None:
        logger.error("promote: proposal %s not found", args.rule_id)
        return 1
    if proposal["status"] != "approved":
        logger.error(
            "promote: only approved proposals can be promoted, got '%s'",
            proposal["status"],
        )
        return 1

    query = str(proposal["proposed_query"])
    severity = extract_severity(query)
    rationale_lines = [ln for ln in str(proposal["rationale"]).strip().splitlines() if ln]
    rule_name = (rationale_lines[0] if rationale_lines else "proposed rule")[:100]

    promoter.insert(
        "security_logs.alert_rules",
        [(rule_name, query, severity, "periodic", 60, 1, "agent", datetime.now(UTC))],
        column_names=[
            "rule_name",
            "query",
            "severity",
            "rule_kind",
            "check_interval",
            "is_active",
            "created_by",
            "last_evaluated",
        ],
    )
    # Отметить предложение как промоутированное: новая версия строки с тем же
    # proposal_id (ReplacingMergeTree заменит старую по updated_at).
    writer.insert(
        "security_logs.rule_proposals",
        [
            (
                proposal["proposal_id"],
                query,
                str(proposal["rationale"]),
                0.0,
                0.0,
                "promoted",
                "promoted to alert_rules",
                proposal["created_at"],
                datetime.now(UTC),
            )
        ],
        column_names=[
            "proposal_id",
            "proposed_query",
            "rationale",
            "hit_rate_sample",
            "estimated_cost",
            "status",
            "validation_log",
            "created_at",
            "updated_at",
        ],
    )
    print(f"promote: {rule_name} (severity={severity})")
    return 0


def cmd_approve_assets(_args: argparse.Namespace) -> int:
    """Перенести готовые asset_proposals в assets (approved + авто по порогу)."""
    from agent.asset_promoter import promote_once

    stats = promote_once(get_reader(), get_writer(), get_asset_promoter())
    print(f"approve-assets: {stats}")
    return 0


def cmd_serve(_args: argparse.Namespace) -> int:
    """Планировщик APScheduler: observer / correlator / rule-engine по интервалам."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from prometheus_client import start_http_server

    from agent.asset_promoter import promote_once as promote_assets_once
    from agent.correlator import run_once as correlate_once
    from agent.observer.observer import run_once as observe_once
    from agent.rule_engine import run_once as propose_once

    # Метрики для Prometheus (порт по умолчанию 9101).
    start_http_server(settings.metrics_port)
    logger.info("serve: metrics on :%d", settings.metrics_port)

    scheduler = BlockingScheduler(timezone="UTC")

    def observe_job() -> None:
        try:
            observe_once(get_reader(), get_writer())
        except Exception as exc:  # noqa: BLE001
            logger.exception("serve: observe failed: %s", exc)

    def correlate_job() -> None:
        try:
            correlate_once(get_reader(), get_promoter())
        except Exception as exc:  # noqa: BLE001
            logger.exception("serve: correlate failed: %s", exc)

    def propose_job() -> None:
        try:
            propose_once(get_reader(), get_writer())
        except Exception as exc:  # noqa: BLE001
            logger.exception("serve: propose failed: %s", exc)

    def asset_promote_job() -> None:
        try:
            promote_assets_once(
                get_reader(),
                get_writer(),
                get_asset_promoter(),
                threshold=settings.asset_auto_promote_threshold,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("serve: asset-promote failed: %s", exc)

    scheduler.add_job(
        observe_job,
        "interval",
        seconds=settings.observer_interval_sec,
        id="observe",
        max_instances=1,
    )
    scheduler.add_job(
        correlate_job,
        "interval",
        seconds=settings.correlator_interval_sec,
        id="correlate",
        max_instances=1,
    )
    scheduler.add_job(
        propose_job,
        "interval",
        seconds=settings.rule_engine_interval_sec,
        id="propose",
        max_instances=1,
    )
    scheduler.add_job(
        asset_promote_job,
        "interval",
        seconds=settings.observer_interval_sec,
        id="asset-promote",
        max_instances=1,
    )

    logger.info(
        "serve: observer=%ss correlator=%ss rule_engine=%ss asset_promote=%ss",
        settings.observer_interval_sec,
        settings.correlator_interval_sec,
        settings.rule_engine_interval_sec,
        settings.observer_interval_sec,
    )
    scheduler.start()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent", description="AppSecGate observer agent")
    parser.add_argument("-v", "--verbose", action="store_true", help="debug logging")
    sub = parser.add_subparsers(dest="command", required=True)

    p_load = sub.add_parser("load-rules", help="load static rules from DIR")
    p_load.add_argument("dir")

    sub.add_parser("observe", help="run Observer once")
    sub.add_parser("correlate", help="run Correlator once")
    sub.add_parser("propose", help="run Rule-Engine once")

    p_promote = sub.add_parser("promote", help="promote approved proposal")
    p_promote.add_argument("rule_id")

    sub.add_parser("approve-assets", help="promote approved/auto assets to inventory")

    sub.add_parser("serve", help="run scheduled agent")
    return parser


_HANDLERS: dict[str, Callable[[argparse.Namespace], int]] = {
    "load-rules": cmd_load_rules,
    "observe": cmd_observe,
    "correlate": cmd_correlate,
    "propose": cmd_propose,
    "promote": cmd_promote,
    "approve-assets": cmd_approve_assets,
    "serve": cmd_serve,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)
    try:
        return _HANDLERS[args.command](args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001 — показываем причину без трейсбека
        logger.error("%s failed: %s", args.command, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
