from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Value, When
from django.utils import timezone

from .models import FollowUp, FollowUpStatus


FOLLOW_UP_FILTERS = ("all", "overdue", "today", "upcoming", "completed")
FOLLOW_UP_PAGE_SIZE = 25


def get_follow_up_inbox(filter_name: str | None, page: int = 1):
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

    try:
        page = max(int(page), 1)
    except (TypeError, ValueError):
        page = 1
    return selected_filter, Paginator(follow_ups, FOLLOW_UP_PAGE_SIZE).get_page(page)
