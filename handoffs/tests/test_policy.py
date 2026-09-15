from decimal import Decimal

import pytest

from handoffs.policy import decide_handoff
from handoffs.roles import check_brief, prepare_brief
from handoffs.types import BriefDraft, OpportunitySnapshot


@pytest.fixture
def snapshot_factory():
    def create(
        fair_code: str | None,
        budget: Decimal | None,
        area: Decimal | None,
        height: Decimal | None,
        maximum: Decimal | None,
    ) -> OpportunitySnapshot:
        return OpportunitySnapshot(
            fair_code=fair_code,
            client_budget_eur=budget,
            stand_area_sqm=area,
            requested_height_m=height,
            max_stand_height_m=maximum,
        )

    return create


@pytest.mark.parametrize(
    ("fair", "budget", "area", "height", "maximum", "decision"),
    [
        (None, Decimal("10000"), Decimal("20"), Decimal("3"), None, "stop_insufficient"),
        ("FAIR-2027", None, Decimal("20"), Decimal("3"), Decimal("5"), "stop_insufficient"),
        ("FAIR-2027", Decimal("10000"), None, Decimal("3"), Decimal("5"), "early_intake"),
        ("FAIR-2027", Decimal("10000"), Decimal("20"), None, Decimal("5"), "early_intake"),
        ("FAIR-2027", Decimal("10000"), Decimal("20"), Decimal("6"), Decimal("5"), "blocked_conflict"),
        ("FAIR-2027", Decimal("10000"), Decimal("20"), Decimal("4"), Decimal("5"), "ready_for_technical"),
    ],
)
def test_handoff_policy(snapshot_factory, fair, budget, area, height, maximum, decision):
    """A wrong decision-table branch must be observable at the coordinator boundary."""
    snapshot = snapshot_factory(fair, budget, area, height, maximum)
    draft = prepare_brief(snapshot)
    check = check_brief(draft, snapshot)
    assert decide_handoff(draft, check).code == decision


def test_checker_rejects_continue_proposal_when_height_conflicts(snapshot_factory):
    """An unsafe continue instruction must be blocked even when supplied outside the preparer."""
    snapshot = snapshot_factory(
        "FAIR-2027", Decimal("10000"), Decimal("20"), Decimal("6"), Decimal("5")
    )
    unsafe = BriefDraft.from_snapshot(
        snapshot, proposed_next_step="Continue with the checked brief to technical."
    )
    result = check_brief(unsafe, snapshot)
    assert result.proposal_is_safe is False
    assert "UNSAFE_PROPOSED_STEP" in {issue.code for issue in result.issues}


def test_unknown_fair_height_limit_stays_in_intake_only(snapshot_factory):
    snapshot = snapshot_factory(
        "FAIR-2027", Decimal("10000"), Decimal("20"), Decimal("4"), None
    )

    draft = prepare_brief(snapshot)
    check = check_brief(draft, snapshot)
    decision = decide_handoff(draft, check)

    assert "UNKNOWN_FAIR_HEIGHT_LIMIT" in {issue.code for issue in check.issues}
    assert any("maximum stand height" in issue.reason.lower() for issue in check.issues)
    assert decision.code == "early_intake"
    assert decision.should_continue is True
    assert decision.allowed_scope == "intake_only"


def test_type_contracts_serialize_decimals_as_json_safe_fixed_point_strings(snapshot_factory):
    """Decimal values must not leak into policy payloads where JSON serialization would fail."""
    snapshot = snapshot_factory(
        "FAIR-2027", Decimal("10000.00"), Decimal("20.50"), Decimal("4.00"), Decimal("5.00")
    )
    draft = prepare_brief(snapshot)
    check = check_brief(draft, snapshot)

    assert snapshot.to_dict()["client_budget_eur"] == "10000.00"
    assert draft.to_dict()["snapshot"]["stand_area_sqm"] == "20.50"
    assert check.to_dict()["issues"] == []
