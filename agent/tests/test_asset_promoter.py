"""Asset auto-promoter tests: candidate selection by the hybrid approval mode."""

from agent.asset_promoter import DEFAULT_THRESHOLD, filter_eligible


def _prop(**kwargs: object) -> dict[str, object]:
    base: dict[str, object] = {
        "proposal_id": "00000000-0000-0000-0000-000000000001",
        "action": "create",
        "asset_key": "external_api:https://api.example.ru/v1",
        "confidence": DEFAULT_THRESHOLD,
        "status": "draft",
    }
    base.update(kwargs)
    return base


class TestFilterEligible:
    def test_draft_at_threshold_auto_promoted(self) -> None:
        assert len(filter_eligible([_prop()], DEFAULT_THRESHOLD)) == 1

    def test_draft_below_threshold_waits(self) -> None:
        rows = [_prop(confidence=0.5)]
        assert filter_eligible(rows, DEFAULT_THRESHOLD) == []

    def test_approved_low_confidence_promoted(self) -> None:
        rows = [_prop(status="approved", confidence=0.1)]
        assert len(filter_eligible(rows, DEFAULT_THRESHOLD)) == 1

    def test_other_statuses_ignored(self) -> None:
        for status in ("validated", "rejected", "promoted", ""):
            assert filter_eligible([_prop(status=status)], DEFAULT_THRESHOLD) == []

    def test_non_create_actions_ignored(self) -> None:
        for action in ("deactivate", "update_owner", "update_criticality"):
            rows = [_prop(action=action, status="approved")]
            assert filter_eligible(rows, DEFAULT_THRESHOLD) == []

    def test_custom_threshold(self) -> None:
        rows = [_prop(confidence=0.8)]
        assert len(filter_eligible(rows, threshold=0.8)) == 1
        assert filter_eligible(rows, threshold=0.9) == []

    def test_bad_confidence_treated_as_zero(self) -> None:
        assert filter_eligible([_prop(confidence="n/a")], DEFAULT_THRESHOLD) == []
