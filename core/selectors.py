from activities.models import FollowUp, FollowUpStatus
from opportunities.models import Opportunity
from django.utils import timezone


DASHBOARD_LIST_LIMIT = 20
RECENT_OPPORTUNITIES_LIMIT = 10


def get_dashboard_follow_ups():
    """Return bounded open follow-ups grouped by their Europe/Rome due date."""
    today = timezone.localdate()
    follow_ups = FollowUp.objects.filter(status=FollowUpStatus.OPEN).select_related(
        "company", "opportunity"
    )

    return {
        "overdue": list(follow_ups.filter(due_on__lt=today).order_by("due_on", "pk")[:DASHBOARD_LIST_LIMIT]),
        "today": list(follow_ups.filter(due_on=today).order_by("pk")[:DASHBOARD_LIST_LIMIT]),
        "upcoming": list(follow_ups.filter(due_on__gt=today).order_by("due_on", "pk")[:DASHBOARD_LIST_LIMIT]),
    }


def get_recent_opportunities():
    return list(
        Opportunity.objects.select_related("company", "fair_edition")
        .order_by("-pk")[:RECENT_OPPORTUNITIES_LIMIT]
    )
