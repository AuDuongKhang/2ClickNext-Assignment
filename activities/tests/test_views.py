from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from activities.models import FollowUp, FollowUpStatus
from crm.models import Company


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


@pytest.mark.django_db
def test_follow_up_inbox_paginates_and_preserves_selected_filter(client, follow_up_factory):
    for number in range(26):
        follow_up_factory(timezone.localdate() + timedelta(days=number + 1), f"Paged {number:02d}")

    first_page = client.get(reverse("follow-up-list"), {"filter": "upcoming"})
    second_page = client.get(
        reverse("follow-up-list"), {"filter": "upcoming", "page": 2}
    )

    assert first_page.context["page_obj"].number == 1
    assert len(first_page.context["follow_ups"]) == 25
    assert first_page.context["page_obj"].has_next() is True
    assert second_page.context["page_obj"].number == 2
    assert len(second_page.context["follow_ups"]) == 1
    assert second_page.context["page_obj"].has_previous() is True
    assert "Paged 25" in second_page.content.decode()
    assert "filter=upcoming&amp;page=2" in first_page.content.decode()
    assert "filter=upcoming&amp;page=1" in second_page.content.decode()


@pytest.mark.django_db
def test_follow_up_inbox_pagination_controls_are_absent_at_page_boundaries(
    client, follow_up_factory
):
    for number in range(26):
        follow_up_factory(
            timezone.localdate() + timedelta(days=number + 1),
            f"Boundary {number:02d}",
        )

    first_page = client.get(reverse("follow-up-list"), {"filter": "upcoming"})
    last_page = client.get(
        reverse("follow-up-list"), {"filter": "upcoming", "page": 2}
    )

    first_content = first_page.content.decode()
    last_content = last_page.content.decode()
    assert 'aria-label="Follow-up inbox pagination"' in first_content
    assert 'rel="prev"' not in first_content
    assert 'rel="next"' in first_content
    assert 'rel="prev"' in last_content
    assert 'rel="next"' not in last_content


@pytest.mark.django_db
def test_follow_up_inbox_links_company_and_opportunity_references(client, follow_up_factory):
    follow_up = follow_up_factory(timezone.localdate(), "Linked follow-up")

    response = client.get(reverse("follow-up-list"), {"filter": "all"})
    content = response.content.decode()

    assert (
        f'href="{reverse("company-detail", args=[follow_up.company.legacy_code])}"'
        in content
    )
    assert (
        f'href="{reverse("opportunity-detail", args=[follow_up.opportunity.legacy_code])}"'
        in content
    )
