"""Persist deterministic handoff-policy evaluations as append-only audit runs."""

from __future__ import annotations

import json

from django.db import transaction

from opportunities.models import Opportunity

from .models import HandoffRun
from .policy import POLICY_VERSION, decide_handoff
from .roles import check_brief, prepare_brief
from .snapshot import build_snapshot


SAFE_FAILURE_MESSAGE = "A handoff role failed before completion."


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
        preparer_output = ""
        reviewer_output = ""

        try:
            draft = prepare_brief(snapshot)
            preparer_output = json.dumps(draft.to_dict(), sort_keys=True)
            check = check_brief(draft, snapshot)
            reviewer_output = json.dumps(check.to_dict(), sort_keys=True)
            decision = decide_handoff(draft, check)
        except Exception as error:
            return HandoffRun.objects.create(
                opportunity=loaded_opportunity,
                snapshot=snapshot_data,
                preparer_output=preparer_output,
                reviewer_output=reviewer_output,
                decision="failed",
                reason="The handoff roles could not complete.",
                policy_version=POLICY_VERSION,
                status="failed",
                should_continue=False,
                allowed_scope="none",
                error_type=type(error).__name__,
                error_message=SAFE_FAILURE_MESSAGE,
            )

        return HandoffRun.objects.create(
            opportunity=loaded_opportunity,
            snapshot=snapshot_data,
            preparer_output=preparer_output,
            reviewer_output=reviewer_output,
            decision=decision.code,
            reason=decision.reason,
            policy_version=POLICY_VERSION,
            status="completed",
            technical_readiness=decision.technical_readiness,
            should_continue=decision.should_continue,
            allowed_scope=decision.allowed_scope,
        )
