from datetime import date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

from handoffs.snapshot import build_snapshot


class RelatedItems:
    def __init__(self, items):
        self.items = items

    def all(self):
        return self.items


def test_build_snapshot_keeps_only_activities_and_follow_ups_for_the_opportunity():
    """Company-wide history must not enter an opportunity handoff snapshot."""
    fair = SimpleNamespace(legacy_code="FAIR-2027", max_stand_height_m=Decimal("5.00"))
    company = SimpleNamespace(legacy_code="CO1", name="Example Exhibitor")
    opportunity = SimpleNamespace(
        legacy_code="OP1",
        company=company,
        fair_edition=fair,
        client_budget_eur=Decimal("10000.00"),
        stand_area_sqm=Decimal("20.00"),
        requested_height_m=Decimal("4.00"),
        description="Launch stand",
        brief_notes="Use reusable materials.",
    )
    own_activity = SimpleNamespace(
        opportunity=opportunity,
        activity_type="call",
        occurred_at=datetime(2027, 1, 1, 9, 0),
        details="Confirmed audience.",
        author="sales.user",
    )
    other_activity = SimpleNamespace(
        opportunity=SimpleNamespace(legacy_code="OP2"),
        activity_type="email",
        occurred_at=datetime(2027, 1, 2, 9, 0),
        details="Other edition.",
        author="sales.user",
    )
    own_follow_up = SimpleNamespace(
        opportunity=opportunity,
        due_on=date(2027, 1, 4),
        summary="Confirm flooring.",
        status="open",
        author="sales.user",
    )
    other_follow_up = SimpleNamespace(
        opportunity=SimpleNamespace(legacy_code="OP2"),
        due_on=date(2027, 1, 5),
        summary="Other edition follow-up.",
        status="open",
        author="sales.user",
    )
    opportunity.activities = RelatedItems([own_activity, other_activity])
    opportunity.follow_ups = RelatedItems([own_follow_up, other_follow_up])

    snapshot = build_snapshot(opportunity)

    assert snapshot.fair_code == "FAIR-2027"
    assert snapshot.commercial_context == {"company_code": "CO1", "company_name": "Example Exhibitor"}
    assert snapshot.customer_requirements == {
        "description": "Launch stand",
        "brief_notes": "Use reusable materials.",
    }
    assert snapshot.recent_interactions == [
        {
            "activity_type": "call",
            "occurred_at": "2027-01-01T09:00:00",
            "details": "Confirmed audience.",
            "author": "sales.user",
        }
    ]
    assert snapshot.open_follow_ups == [
        {
            "due_on": "2027-01-04",
            "summary": "Confirm flooring.",
            "status": "open",
            "author": "sales.user",
        }
    ]


def test_build_snapshot_limits_and_orders_recent_activities():
    """A brief must contain the bounded newest activity window, not database-order history."""
    fair = SimpleNamespace(legacy_code="FAIR-2027", max_stand_height_m=Decimal("5.00"))
    opportunity = SimpleNamespace(
        pk=1,
        company=SimpleNamespace(legacy_code="CO1", name="Example Exhibitor"),
        fair_edition=fair,
        client_budget_eur=Decimal("10000.00"),
        stand_area_sqm=Decimal("20.00"),
        requested_height_m=Decimal("4.00"),
        description="Launch stand",
        brief_notes="",
    )
    activities = [
        SimpleNamespace(
            pk=index,
            opportunity=opportunity,
            activity_type="note",
            occurred_at=datetime(2027, 1, 1) + timedelta(days=index),
            details=f"Activity {index}",
            author="sales.user",
        )
        for index in range(52)
    ]
    opportunity.activities = RelatedItems(list(reversed(activities)))
    opportunity.follow_ups = RelatedItems([])

    snapshot = build_snapshot(opportunity)

    assert len(snapshot.recent_interactions) == 50
    assert [item["details"] for item in snapshot.recent_interactions] == [
        f"Activity {index}" for index in range(51, 1, -1)
    ]
