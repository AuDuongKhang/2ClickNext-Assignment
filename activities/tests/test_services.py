from datetime import date, timedelta

import pytest
from django.utils import timezone

from activities.models import FollowUp, FollowUpStatus
from activities.services import complete_follow_up, record_conversation


@pytest.mark.django_db
def test_record_conversation_can_schedule_a_follow_up(opportunity):
    activity, follow_up = record_conversation(
        opportunity=opportunity,
        activity_type="call",
        occurred_at=timezone.now(),
        details="Customer will confirm the floor area",
        author="Sales user",
        follow_up_on=date.today() + timedelta(days=2),
        follow_up_summary="Confirm floor area",
    )

    assert activity.opportunity == opportunity
    follow_up = FollowUp.objects.get(pk=follow_up.pk)
    follow_up.refresh_from_db()
    assert follow_up.source_activity == activity
    assert follow_up.company == opportunity.company
    assert follow_up.status == "open"


@pytest.mark.django_db
def test_complete_follow_up_is_idempotent(follow_up_factory):
    follow_up = follow_up_factory(due_on=timezone.localdate(), summary="Call customer")

    complete_follow_up(follow_up)
    first_completed_at = follow_up.completed_at
    complete_follow_up(follow_up)
    follow_up.refresh_from_db()

    assert follow_up.status == "completed"
    assert follow_up.completed_at == first_completed_at


@pytest.mark.django_db
def test_complete_follow_up_preserves_concurrent_completion(follow_up_factory):
    follow_up = follow_up_factory(due_on=timezone.localdate(), summary="Call customer")
    stale_follow_up = FollowUp.objects.get(pk=follow_up.pk)
    first_completed_at = timezone.now() - timedelta(minutes=5)
    FollowUp.objects.filter(pk=follow_up.pk).update(
        status=FollowUpStatus.COMPLETED,
        completed_at=first_completed_at,
    )

    complete_follow_up(stale_follow_up)
    stale_follow_up.refresh_from_db()

    assert stale_follow_up.status == FollowUpStatus.COMPLETED
    assert stale_follow_up.completed_at == first_completed_at


@pytest.mark.django_db
def test_opportunity_conversation_inherits_company(opportunity):
    activity, _ = record_conversation(
        opportunity=opportunity,
        activity_type="email",
        occurred_at=timezone.now(),
        details="Budget confirmed",
        author="Sales user",
        follow_up_on=None,
        follow_up_summary="",
    )

    assert activity.company == opportunity.company
