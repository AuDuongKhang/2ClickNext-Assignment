from decimal import Decimal
import json
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
    opportunity.client_budget_eur = Decimal("10000.00")
    opportunity.save(update_fields=["client_budget_eur"])
    previous_notes = opportunity.brief_notes

    run = run_handoff(opportunity)

    opportunity.refresh_from_db()
    assert run.technical_readiness == "early_intake"
    assert opportunity.brief_notes == previous_notes


@pytest.mark.django_db
def test_completed_run_persists_coordinator_continuation_and_scope(opportunity):
    opportunity.client_budget_eur = Decimal("10000.00")
    opportunity.stand_area_sqm = Decimal("80.00")
    opportunity.requested_height_m = Decimal("4.00")
    opportunity.save(update_fields=["client_budget_eur", "stand_area_sqm", "requested_height_m"])

    run = run_handoff(opportunity)
    run.refresh_from_db()

    assert run.should_continue is True
    assert run.allowed_scope == "technical_work"


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
    assert failed.should_continue is False
    assert failed.allowed_scope == "none"


@pytest.mark.django_db
def test_checker_failure_preserves_preparer_output_and_appends_run(monkeypatch, opportunity):
    """A checker failure must retain the completed preparer output in a new failed row."""
    completed = run_handoff(opportunity)
    monkeypatch.setattr(
        "handoffs.services.check_brief", Mock(side_effect=RuntimeError("checker failed"))
    )

    failed = run_handoff(opportunity)

    completed.refresh_from_db()
    assert completed.status == "completed"
    assert failed.status == "failed"
    assert json.loads(failed.preparer_output)["proposed_next_step"]
    assert failed.reviewer_output == ""


@pytest.mark.django_db
def test_coordinator_failure_preserves_preparer_and_reviewer_outputs(monkeypatch, opportunity):
    """A coordinator failure must retain both earlier role outputs in a new failed row."""
    completed = run_handoff(opportunity)
    monkeypatch.setattr(
        "handoffs.services.decide_handoff", Mock(side_effect=RuntimeError("coordinator failed"))
    )

    failed = run_handoff(opportunity)

    completed.refresh_from_db()
    assert completed.status == "completed"
    assert failed.status == "failed"
    assert json.loads(failed.preparer_output)["proposed_next_step"]
    assert "MISSING_BUDGET" in {
        issue["code"] for issue in json.loads(failed.reviewer_output)["issues"]
    }


@pytest.mark.django_db
def test_sensitive_role_error_is_not_persisted_or_rendered(monkeypatch, client, opportunity):
    """Role diagnostics must be replaced by a bounded safe message at every boundary."""
    sensitive_message = "password=secret C:\\private\\crm.sqlite SELECT * FROM contacts"
    monkeypatch.setattr(
        "handoffs.services.prepare_brief", Mock(side_effect=RuntimeError(sensitive_message))
    )

    failed = run_handoff(opportunity)
    response = client.get(f"/handoffs/{failed.pk}/")

    assert failed.error_message == "A handoff role failed before completion."
    assert sensitive_message not in failed.error_message
    assert sensitive_message not in response.content.decode()
