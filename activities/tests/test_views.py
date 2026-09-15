from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from activities.models import FollowUpStatus


@pytest.mark.django_db
def test_conversation_form_records_activity_and_follow_up(client, opportunity):
    response = client.post(
        reverse("conversation-new", args=[opportunity.legacy_code]),
        {
            "activity_type": "call",
            "occurred_at": "15/09/2026 09:30",
            "details": "Customer will confirm the floor area",
            "follow_up_on": "17/09/2026",
            "follow_up_summary": "Confirm floor area",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("opportunity-detail", args=[opportunity.legacy_code])
    follow_up = opportunity.follow_ups.get(summary="Confirm floor area")
    assert follow_up.company == opportunity.company
    assert follow_up.due_on.isoformat() == "2026-09-17"
    assert [str(message) for message in get_messages(response.wsgi_request)] == [
        "Conversation recorded."
    ]


@pytest.mark.django_db
def test_follow_up_form_allows_an_undated_opportunity_task(client, opportunity):
    response = client.post(
        reverse("follow-up-new", args=[opportunity.legacy_code]),
        {"due_on": "", "summary": "Confirm floor area"},
    )

    assert response.status_code == 302
    follow_up = opportunity.follow_ups.get(summary="Confirm floor area")
    assert follow_up.due_on is None
    assert [str(message) for message in get_messages(response.wsgi_request)] == [
        "Follow-up scheduled."
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("filter_name", "due_offset", "status", "expected_summary"),
    [
        ("overdue", -1, FollowUpStatus.OPEN, "Overdue"),
        ("today", 0, FollowUpStatus.OPEN, "Today"),
        ("upcoming", 1, FollowUpStatus.OPEN, "Upcoming"),
        ("completed", 0, FollowUpStatus.COMPLETED, "Completed"),
    ],
)
def test_follow_up_inbox_filters_by_due_date_and_status(
    client, follow_up_factory, filter_name, due_offset, status, expected_summary
):
    today = timezone.localdate()
    matching = follow_up_factory(today + timedelta(days=due_offset), expected_summary)
    matching.status = status
    matching.save(update_fields=["status"])
    other = follow_up_factory(today + timedelta(days=3), "Other")
    other.status = (
        FollowUpStatus.OPEN
        if status == FollowUpStatus.COMPLETED
        else FollowUpStatus.COMPLETED
    )
    other.save(update_fields=["status"])

    response = client.get(reverse("follow-up-list"), {"filter": filter_name})

    assert response.status_code == 200
    assert expected_summary in response.content.decode()
    assert "Other" not in response.content.decode()


@pytest.mark.django_db
def test_complete_follow_up_is_post_only_and_returns_to_inbox(client, follow_up_factory):
    follow_up = follow_up_factory(timezone.localdate(), "Call customer")
    url = reverse("follow-up-complete", args=[follow_up.pk])

    assert client.get(url).status_code == 405
    response = client.post(url)

    follow_up.refresh_from_db()
    assert response.status_code == 302
    assert response.url == reverse("follow-up-list")
    assert follow_up.status == FollowUpStatus.COMPLETED
    assert [str(message) for message in get_messages(response.wsgi_request)] == [
        "Follow-up completed."
    ]


@pytest.mark.django_db
def test_follow_up_inbox_orders_open_items_before_completed_items(
    client, follow_up_factory
):
    completed = follow_up_factory(timezone.localdate(), "Completed first by date")
    completed.status = FollowUpStatus.COMPLETED
    completed.save(update_fields=["status"])
    open_follow_up = follow_up_factory(
        timezone.localdate() + timedelta(days=1), "Open first by status"
    )

    response = client.get(reverse("follow-up-list"))

    assert list(response.context["follow_ups"]) == [open_follow_up, completed]
