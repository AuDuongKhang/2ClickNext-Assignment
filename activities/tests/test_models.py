from datetime import date

import pytest


@pytest.mark.django_db
def test_follow_up_factory_keeps_legacy_task_time_and_author(follow_up_factory):
    follow_up = follow_up_factory(date(2027, 5, 4), "Confirm plot area")

    assert follow_up.due_on == date(2027, 5, 4)
    assert follow_up.summary == "Confirm plot area"
    assert follow_up.created_at is not None
    assert follow_up.author == "sales.user"
