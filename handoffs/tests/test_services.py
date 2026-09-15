from decimal import Decimal
from unittest.mock import Mock

import pytest

from handoffs.services import run_handoff


@pytest.mark.django_db
def test_rerun_keeps_old_snapshot_and_creates_new_result(opportunity):
    """A rerun must append a fresh audit record instead of overwriting its input evidence."""
    opportunity.client_budget_eur = Decimal("10000.00")
    opportunity.save(update_fields=["client_budget_eur"])

    first = run_handoff(opportunity)
    original_snapshot = first.snapshot.copy()
    opportunity.stand_area_sqm = Decimal("80.00")
    opportunity.requested_height_m = Decimal("4.00")
    opportunity.save()

    second = run_handoff(opportunity)

    first.refresh_from_db()
    assert first.snapshot == original_snapshot
    assert first.pk != second.pk
    assert second.decision == "ready_for_technical"


@pytest.mark.django_db
def test_completed_run_updates_only_technical_readiness(opportunity):
    """A completed assistant run must not alter user-maintained brief fields."""
    previous_notes = opportunity.brief_notes

    run = run_handoff(opportunity)

    opportunity.refresh_from_db()
    assert run.technical_readiness == "blocked"
    assert opportunity.brief_notes == previous_notes


@pytest.mark.django_db
def test_role_failure_is_audited_without_changing_previous_run(monkeypatch, opportunity):
    """An unexpected role error must become a safe, append-only audit row."""
    completed = run_handoff(opportunity)
    monkeypatch.setattr(
        "handoffs.services.prepare_brief", Mock(side_effect=RuntimeError("role failed"))
    )

    failed = run_handoff(opportunity)

    completed.refresh_from_db()
    assert completed.status == "completed"
    assert failed.status == "failed"
    assert failed.error_type == "RuntimeError"
    assert "Traceback" not in failed.error_message
