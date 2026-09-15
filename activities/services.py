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
def schedule_follow_up(
    *, company, opportunity=None, source_activity=None, due_on=None, summary, author
):
    return FollowUp.objects.create(
        company=company,
        opportunity=opportunity,
        source_activity=source_activity,
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
            source_activity=activity,
            due_on=follow_up_on,
            summary=follow_up_summary,
            author=author,
        )
    return activity, follow_up


@transaction.atomic
def complete_follow_up(follow_up):
    current = FollowUp.objects.select_for_update().get(pk=follow_up.pk)
    if current.status == FollowUpStatus.OPEN:
        current.status = FollowUpStatus.COMPLETED
        current.completed_at = timezone.now()
        current.save(update_fields=["status", "completed_at"])
    follow_up.status = current.status
    follow_up.completed_at = current.completed_at
    return follow_up
