from datetime import timedelta

import pytest
from django.utils import timezone


@pytest.mark.django_db
def test_dashboard_separates_overdue_today_and_upcoming(client, follow_up_factory):
    today = timezone.localdate()
    follow_up_factory(due_on=today - timedelta(days=1), summary="Overdue")
    follow_up_factory(due_on=today, summary="Today")
    follow_up_factory(due_on=today + timedelta(days=2), summary="Upcoming")

    response = client.get("/")

    assert [item.summary for item in response.context["overdue"]] == ["Overdue"]
    assert [item.summary for item in response.context["today"]] == ["Today"]
    assert [item.summary for item in response.context["upcoming"]] == ["Upcoming"]
