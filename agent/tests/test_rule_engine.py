"""Rule-Engine tests: parsing the LLM JSON answer."""

import json

from agent.rule_engine import _extract_proposals

QUERY = "SELECT count() AS n FROM security_logs.assets WHERE asset_type = 'host'"


class TestExtractProposals:
    def test_valid_json(self) -> None:
        text = json.dumps(
            {"proposals": [{"rationale": "Shadow host", "query": QUERY}]},
            ensure_ascii=False,
        )
        result = _extract_proposals(text)
        assert len(result) == 1
        assert result[0]["query"] == QUERY
        assert result[0]["rationale"] == "Shadow host"

    def test_json_embedded_in_markdown(self) -> None:
        text = (
            "Here are the rules:\n```json\n"
            + json.dumps({"proposals": [{"rationale": "R", "query": QUERY}]})
            + "\n```\n"
        )
        assert len(_extract_proposals(text)) == 1

    def test_no_json(self) -> None:
        assert _extract_proposals("sorry, nothing found") == []

    def test_malformed_json(self) -> None:
        assert _extract_proposals("{not valid json}") == []

    def test_skips_items_without_query(self) -> None:
        text = json.dumps(
            {
                "proposals": [
                    {"rationale": "no query"},
                    {"query": QUERY, "rationale": "ok"},
                ]
            }
        )
        result = _extract_proposals(text)
        assert len(result) == 1
        assert result[0]["rationale"] == "ok"

    def test_non_list_proposals(self) -> None:
        assert _extract_proposals('{"proposals": "nope"}') == []
