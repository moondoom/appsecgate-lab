"""Тесты Observer: извлечение кандидатов-активов из spend_logs."""

from agent.observer.observer import extract_candidates


def _row(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "api_base": "",
        "user": "",
        "end_user": "",
        "model": "p/deepseek-v4-flash",
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

    def test_ai_agent_and_user(self) -> None:
        rows = [_row(user="cline", end_user="alice@corp")]
        cands = extract_candidates(rows)
        by_type = {c.asset_type: c for c in cands}
        assert by_type["ai_agent"].asset_key == "ai_agent:cline"
        assert by_type["user"].asset_key == "user:alice@corp"

    def test_duplicates_collapsed(self) -> None:
        rows = [
            _row(api_base="https://api.prov_1.ru/v1"),
            _row(api_base="https://api.prov_1.ru/v1/"),
        ]
        cands = extract_candidates(rows)
        assert len(cands) == 1

    def test_empty_rows_ignored(self) -> None:
        assert extract_candidates([_row(), _row(user=" "), _row(api_base="")]) == []

    def test_multiple_assets_from_one_row(self) -> None:
        rows = [_row(api_base="https://api.x/v1", user="agent1", end_user="u1")]
        cands = extract_candidates(rows)
        assert len(cands) == 3
