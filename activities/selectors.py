from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from .models import FollowUp, FollowUpStatus


FOLLOW_UP_FILTERS = ("all", "overdue", "today", "upcoming", "completed")


def get_follow_up_inbox(filter_name: str | None):
    selected_filter = filter_name if filter_name in FOLLOW_UP_FILTERS else "all"
    follow_ups = (
        FollowUp.objects.select_related("company", "opportunity")
        .annotate(
            status_rank=Case(
                When(status=FollowUpStatus.OPEN, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            )
        )
        .order_by("status_rank", "due_on", "pk")
    )
    today = timezone.localdate()

    if selected_filter == "overdue":
        follow_ups = follow_ups.filter(status=FollowUpStatus.OPEN, due_on__lt=today)
    elif selected_filter == "today":
        follow_ups = follow_ups.filter(status=FollowUpStatus.OPEN, due_on=today)
    elif selected_filter == "upcoming":
        follow_ups = follow_ups.filter(status=FollowUpStatus.OPEN, due_on__gt=today)
    elif selected_filter == "completed":
        follow_ups = follow_ups.filter(status=FollowUpStatus.COMPLETED)

    return selected_filter, follow_ups
