"""Persist deterministic handoff-policy evaluations as append-only audit runs."""

from __future__ import annotations

import json

from django.db import transaction

from opportunities.models import Opportunity

from .models import HandoffRun
from .policy import POLICY_VERSION, decide_handoff
from .roles import check_brief, prepare_brief
from .snapshot import build_snapshot


def _safe_error_message(error: Exception) -> str:
    message = str(error).splitlines()[0] if str(error) else "Unexpected role failure."
    if "traceback" in message.lower():
        return "Unexpected role failure."
    return message


def run_handoff(opportunity: Opportunity) -> HandoffRun:
    """Evaluate one opportunity and append its durable, display-safe handoff record."""
    with transaction.atomic():
        loaded_opportunity = (
            Opportunity.objects.select_related("company", "primary_contact", "fair_edition")
            .prefetch_related("activities", "follow_ups")
            .get(pk=opportunity.pk)
        )
        snapshot = build_snapshot(loaded_opportunity)
        snapshot_data = snapshot.to_dict()

        try:
            draft = prepare_brief(snapshot)
            check = check_brief(draft, snapshot)
            decision = decide_handoff(draft, check)
        except Exception as error:
            return HandoffRun.objects.create(
                opportunity=loaded_opportunity,
                snapshot=snapshot_data,
                decision="failed",
                reason="The handoff roles could not complete.",
                policy_version=POLICY_VERSION,
                status="failed",
                error_type=type(error).__name__,
                error_message=_safe_error_message(error),
            )

        return HandoffRun.objects.create(
            opportunity=loaded_opportunity,
            snapshot=snapshot_data,
            preparer_output=json.dumps(draft.to_dict(), sort_keys=True),
            reviewer_output=json.dumps(check.to_dict(), sort_keys=True),
            decision=decision.code,
            reason=decision.reason,
            policy_version=POLICY_VERSION,
            status="completed",
            technical_readiness=decision.technical_readiness,
        )
