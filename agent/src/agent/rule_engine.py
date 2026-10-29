"""Rule-Engine: генерирует rule_proposals через LLM (хост-LiteLLM).

Контекст собирается из ClickHouse (инциденты, правила, активы), промпт
уходит на ``settings.litellm_base_url`` (прокси на хосте) моделью
``settings.agent_model``. Ответ обязан быть JSON со списком правил;
каждое предложение проходит Validator перед записью.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from typing import Any

import httpx
from clickhouse_connect.driver import Client

from agent.config import settings
from agent.metrics import rule_engine_llm_latency, rule_engine_proposals, validator_rejections
from agent.validator import validate_sql

logger = logging.getLogger(__name__)

_PROPOSAL_COLUMNS = [
    "proposed_query",
    "rationale",
    "hit_rate_sample",
    "estimated_cost",
    "validation_log",
]

_LLM_TIMEOUT_SEC = 60.0
_MAX_PROPOSALS = 3

_SYSTEM_PROMPT = """Ты — Rule-Engine для SIEM-подобной системы на ClickHouse. \
Твоя задача — предложить новые правила детекта по статистике инцидентов и инвентаря. \
Ответь строго JSON: {"proposals": [{"rationale": str, "query": "SELECT ..."}]}.

Доступные таблицы (только они, с полным префиксом):
security_logs.audit_events, security_logs.agent_tool_calls, security_logs.assets,
security_logs.mcp_tools, security_logs.asset_tool_bindings,
security_logs.alert_rules, security_logs.alert_incidents.

Требования к SQL:
* один SELECT, без точки с запятой и без нескольких statement'ов;
* всегда полностью квалифицированное имя: security_logs.<table>;
* в SELECT обязательны 'high'|'medium'|'low' AS severity, triggered_value, context;
* запрещены функции file/url/s3/remote/mysql и любые обращения к внешним источникам.

Пример валидного правила:
SELECT a.asset_key, 'medium' AS severity, 1 AS triggered_value,
       format('{{"host":"{}"}}', a.asset_key) AS context
FROM security_logs.assets AS a WHERE a.last_seen < now() - INTERVAL 7 DAY"""


def _build_prompt(context: Mapping[str, Any]) -> str:
    return (
        "Контекст системы:\n"
        f"- активных правил: {context['active_rules']}\n"
        f"- инцидентов за 24ч: {context['incidents_24h']}\n"
        f"- активов в инвентаре: {context['assets_total']}\n"
        f"- топ severities: {context['severity_top']}\n"
        "Предложи до 3 детект-правил по этим данным, строго по требованиям выше.\n"
    )


def _collect_context(reader: Client) -> dict[str, Any]:
    active_rules = reader.query(
        "SELECT count() AS n FROM security_logs.alert_rules WHERE is_active = 1"
    ).first_item or {"n": 0}
    incidents = reader.query(
        "SELECT count() AS n FROM security_logs.alert_incidents "
        "WHERE triggered_at >= now() - INTERVAL 1 DAY"
    ).first_item or {"n": 0}
    assets = reader.query("SELECT count() AS n FROM security_logs.assets FINAL").first_item or {
        "n": 0
    }
    severity_top = list(
        reader.query(
            "SELECT severity, count() AS n FROM security_logs.alert_incidents "
            "WHERE triggered_at >= now() - INTERVAL 1 DAY GROUP BY severity ORDER BY n DESC LIMIT 3"
        ).named_results()
    )
    return {
        "active_rules": int(active_rules["n"]),
        "incidents_24h": int(incidents["n"]),
        "assets_total": int(assets["n"]),
        "severity_top": severity_top or [],
    }


def _call_llm(prompt: str) -> str:
    """Один аккуратный вызов хост-LiteLLM."""
    url = f"{settings.litellm_base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": settings.agent_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1200,
    }
    headers = {"Authorization": f"Bearer {settings.litellm_api_key}"}
    with httpx.Client(timeout=_LLM_TIMEOUT_SEC) as client, rule_engine_llm_latency.time():
        response = client.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()
    message = data["choices"][0]["message"]
    # reasoning-модели (glm-4.7-flash через ollama) отдают текст в
    # reasoning_content при пустом content — берём фолбэк.
    content = message.get("content") or message.get("reasoning_content") or ""
    return str(content)


def _extract_proposals(text: str) -> list[dict[str, str]]:
    """Извлечь список предложений из JSON-ответа LLM."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return []
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    raw = payload.get("proposals", [])
    if not isinstance(raw, list):
        return []
    proposals: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict) and item.get("query") and item.get("rationale"):
            proposals.append({"rationale": str(item["rationale"]), "query": str(item["query"])})
    return proposals


def _write_proposals(writer: Client, proposals: Sequence[dict[str, str]]) -> None:
    rows = [(p["query"], p["rationale"], 0.0, 0.0, "validated") for p in proposals]
    if rows:
        writer.insert("security_logs.rule_proposals", rows, column_names=_PROPOSAL_COLUMNS)


def run_once(reader: Client, writer: Client) -> dict[str, Any]:
    """Один проход Rule-Engine. Возвращает счётчики и отклонения."""
    context = _collect_context(reader)
    prompt = _build_prompt(context)
    try:
        answer = _call_llm(prompt)
    except Exception as exc:  # noqa: BLE001 — LLM недоступен — это внешний сервис
        logger.error("rule_engine: LLM call failed: %s", exc)
        return {"proposals": 0, "rejected": [], "error": str(exc)}

    proposed = _extract_proposals(answer)
    accepted: list[dict[str, str]] = []
    rejected: list[str] = []
    for p in proposed[:_MAX_PROPOSALS]:
        ok, reason = validate_sql(p["query"])
        if ok:
            accepted.append(p)
            rule_engine_proposals.labels("draft").inc()
        else:
            rejected.append(reason)
            validator_rejections.labels(reason).inc()
            logger.warning("rule_engine: proposal rejected (%s): %.80s", reason, p["query"])

    _write_proposals(writer, accepted)
    logger.info("rule_engine: %d accepted, %d rejected", len(accepted), len(rejected))
    return {"proposals": len(accepted), "rejected": rejected}
