"""Тесты Observer: извлечение кандидатов-активов из витрин security_logs."""

from agent.observer.observer import (
    extract_candidates,
    extract_guardrail_candidates,
    extract_tool_candidates,
)


def _row(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "api_base": "",
        "user_id": "",
        "end_user": "",
        "model": "p/deepseek-v4-flash",
        "model_group": "p/deepseek-v4-flash",
        "custom_llm_provider": "openai",
        "tool_calls_count": 0,
        "guardrails_count": 0,
        "requester_ip": "",
        "user_agent": "",
    }
    base.update(kwargs)
    return base


class TestExtractCandidates:
    def test_external_api(self) -> None:
        rows = [_row(api_base="https://api.prov_1.ru/v1/")]
        cands = extract_candidates(rows)
        assert len(cands) == 1
        assert cands[0].asset_type == "external_api"
        assert cands[0].asset_key == "external_api:https://api.prov_1.ru/v1"
        assert cands[0].display_name == "https://api.prov_1.ru/v1/"
        assert cands[0].attributes["observed_in"] == "security_logs.spend_logs_extended"

    def test_external_api_enriched(self) -> None:
        rows = [
            _row(
                api_base="https://api.prov_1.ru/v1",
                model="openai/deepseek/deepseek-v4-flash-0731",
                model_group="p/deepseek-v4-flash",
                custom_llm_provider="openai",
            )
        ]
        cand = extract_candidates(rows)[0]
        assert cand.attributes["model"] == "openai/deepseek/deepseek-v4-flash-0731"
        assert cand.attributes["model_group"] == "p/deepseek-v4-flash"
        assert cand.attributes["custom_llm_provider"] == "openai"

    def test_ai_agent_and_user(self) -> None:
        rows = [_row(user_id="cline", end_user="alice@corp")]
        by_type = {c.asset_type: c for c in extract_candidates(rows)}
        assert by_type["ai_agent"].asset_key == "ai_agent:cline"
        assert by_type["user"].asset_key == "user:alice@corp"

    def test_ai_agent_enriched(self) -> None:
        rows = [
            _row(
                user_id="cline",
                requester_ip="10.0.0.5",
                user_agent="ai-sdk-openai-compatible/3.0.67",
                tool_calls_count=7,
                guardrails_count=3,
            )
        ]
        cand = extract_candidates(rows)[0]
        assert cand.attributes["requester_ip"] == "10.0.0.5"
        assert cand.attributes["user_agent"] == "ai-sdk-openai-compatible/3.0.67"
        assert cand.attributes["tool_calls_count"] == 7
        assert cand.attributes["guardrails_count"] == 3

    def test_duplicates_collapsed(self) -> None:
        rows = [
            _row(api_base="https://api.prov_1.ru/v1"),
            _row(api_base="https://api.prov_1.ru/v1/"),
        ]
        cands = extract_candidates(rows)
        assert len(cands) == 1

    def test_empty_rows_ignored(self) -> None:
        assert extract_candidates([_row(), _row(user_id=" "), _row(api_base="")]) == []

    def test_multiple_assets_from_one_row(self) -> None:
        rows = [_row(api_base="https://api.x/v1", user_id="agent1", end_user="u1")]
        cands = extract_candidates(rows)
        assert len(cands) == 3


class TestExtractToolCandidates:
    def test_tool_candidate(self) -> None:
        rows = [
            {
                "tool_name": "run_commands",
                "user_id": "default_user_id",
                "model": "p/deepseek-v4-flash",
                "calls": 42,
            }
        ]
        cands = extract_tool_candidates(rows)
        assert len(cands) == 1
        cand = cands[0]
        assert cand.asset_type == "tool"
        assert cand.asset_key == "tool:run_commands"
        assert cand.display_name == "run_commands"
        assert cand.attributes["observed_in"] == "security_logs.events_tool_calls"
        assert cand.attributes["calls"] == 42

    def test_tool_empty_ignored(self) -> None:
        rows = [{"tool_name": "", "calls": 1}, {"tool_name": "  ", "calls": 2}]
        assert extract_tool_candidates(rows) == []

    def test_tool_duplicates_collapsed(self) -> None:
        rows = [
            {"tool_name": "run_commands", "user_id": "a", "model": "m1", "calls": 5},
            {"tool_name": "run_commands", "user_id": "b", "model": "m2", "calls": 3},
        ]
        cands = extract_tool_candidates(rows)
        assert len(cands) == 1
        assert cands[0].attributes["calls"] == 5


class TestExtractGuardrailCandidates:
    def test_guardrail_candidate(self) -> None:
        rows = [
            {
                "guardrail_name": "presidio-pii-mask",
                "guardrail_provider": "presidio",
                "guardrail_mode": "pre_call",
                "action": "MASK",
                "firings": 7,
            }
        ]
        cands = extract_guardrail_candidates(rows)
        assert len(cands) == 1
        cand = cands[0]
        assert cand.asset_type == "guardrail"
        assert cand.asset_key == "guardrail:presidio-pii-mask"
        assert cand.display_name == "presidio-pii-mask"
        assert cand.attributes["observed_in"] == "security_logs.events_guardrails"
        assert cand.attributes["provider"] == "presidio"
        assert cand.attributes["mode"] == "pre_call"
        assert cand.attributes["action"] == "MASK"
        assert cand.attributes["firings"] == 7

    def test_guardrail_empty_ignored(self) -> None:
        assert extract_guardrail_candidates([{"guardrail_name": "", "firings": 1}]) == []

