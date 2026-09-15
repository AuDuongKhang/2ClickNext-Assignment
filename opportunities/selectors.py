from dataclasses import dataclass

from activities.models import Activity, FollowUp, FollowUpStatus
from handoffs.models import HandoffRun

from .models import Opportunity


WORKSPACE_LIST_LIMIT = 50


@dataclass(frozen=True)
class OpportunityWorkspace:
    opportunity: Opportunity
    activities: list[Activity]
    open_follow_ups: list[FollowUp]
    handoff_runs: list[HandoffRun]

    @property
    def requested_height_exceeds_maximum(self) -> bool:
        requested_height = self.opportunity.requested_height_m
        maximum_height = self.opportunity.fair_edition.max_stand_height_m
        return (
            requested_height is not None
            and maximum_height is not None
            and requested_height > maximum_height
        )


def get_opportunity_workspace(legacy_code: str) -> OpportunityWorkspace:
    """Load one opportunity and its bounded, opportunity-scoped workspace data."""
    opportunity = (
        Opportunity.objects.select_related("company", "primary_contact", "fair_edition")
        .filter(legacy_code=legacy_code)
        .first()
    )
    if opportunity is None:
        raise Opportunity.DoesNotExist

    activities = list(
        Activity.objects.filter(opportunity=opportunity)
        .select_related("company")
        .order_by("-occurred_at", "-pk")[:WORKSPACE_LIST_LIMIT]
    )
    open_follow_ups = list(
        FollowUp.objects.filter(opportunity=opportunity, status=FollowUpStatus.OPEN)
        .order_by("due_on", "-created_at", "-pk")[:WORKSPACE_LIST_LIMIT]
    )
    handoff_runs = list(
        HandoffRun.objects.filter(opportunity=opportunity)
        .order_by("-created_at", "-pk")[:WORKSPACE_LIST_LIMIT]
    )
    return OpportunityWorkspace(
        opportunity=opportunity,
        activities=activities,
        open_follow_ups=open_follow_ups,
        handoff_runs=handoff_runs,
    )
