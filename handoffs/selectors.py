"""Read models for persisted handoff audit records."""

from .models import HandoffRun


def get_handoff_run(pk: int) -> HandoffRun:
    return HandoffRun.objects.select_related(
        "opportunity__company", "opportunity__primary_contact", "opportunity__fair_edition"
    ).get(pk=pk)
