from datetime import date

import pytest

from activities.models import Activity


@pytest.mark.django_db
def test_follow_up_factory_keeps_legacy_task_time_and_author(follow_up_factory):
    follow_up = follow_up_factory(date(2027, 5, 4), "Confirm plot area")

    assert follow_up.due_on == date(2027, 5, 4)
    assert follow_up.summary == "Confirm plot area"
    assert follow_up.created_at is not None
    assert follow_up.author == "sales.user"


@pytest.mark.django_db
def test_activity_preserves_imported_author(activity_factory, opportunity):
    activity = activity_factory(opportunity, "Confirmed artwork")
    activity.author = "archive.sales"
    activity.save(update_fields=["author"])

    assert Activity.objects.get(pk=activity.pk).author == "archive.sales"


@pytest.mark.django_db
def test_follow_up_status_defaults_open_and_can_be_completed(follow_up_factory):
    follow_up = follow_up_factory(date(2027, 5, 4), "Confirm plot area")

    assert follow_up.status == "open"
    follow_up.status = "completed"
    follow_up.save(update_fields=["status"])
    assert follow_up.status == "completed"
