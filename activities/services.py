from uuid import uuid4

from django.db import transaction
from django.utils import timezone

from .models import Activity, ActivityType, FollowUp, FollowUpStatus


CONVERSATION_TYPES = {
    ActivityType.CALL,
    ActivityType.EMAIL,
    ActivityType.MEETING,
}


def _local_legacy_code() -> str:
    return f"local-{uuid4().hex}"


@transaction.atomic
def schedule_follow_up(*, company, opportunity=None, due_on=None, summary, author):
    return FollowUp.objects.create(
        company=company,
        opportunity=opportunity,
        due_on=due_on,
        summary=summary,
        created_at=timezone.now(),
        author=author,
        status=FollowUpStatus.OPEN,
    )


@transaction.atomic
def record_conversation(
    *,
    opportunity,
    activity_type,
    occurred_at,
    details,
    author,
    follow_up_on,
    follow_up_summary,
):
    if activity_type not in CONVERSATION_TYPES:
        raise ValueError("Conversation activity type must be call, email, or meeting.")

    activity = Activity.objects.create(
        legacy_code=_local_legacy_code(),
        company=opportunity.company,
        opportunity=opportunity,
        activity_type=activity_type,
        occurred_at=occurred_at,
        details=details,
        author=author,
    )
    follow_up = None
    if follow_up_on and follow_up_summary:
        follow_up = schedule_follow_up(
            company=opportunity.company,
            opportunity=opportunity,
            due_on=follow_up_on,
            summary=follow_up_summary,
            author=author,
        )
        follow_up.source_activity = activity
    return activity, follow_up


@transaction.atomic
def complete_follow_up(follow_up):
    if follow_up.status == FollowUpStatus.OPEN:
        follow_up.status = FollowUpStatus.COMPLETED
        follow_up.completed_at = timezone.now()
        follow_up.save(update_fields=["status", "completed_at"])
    return follow_up
