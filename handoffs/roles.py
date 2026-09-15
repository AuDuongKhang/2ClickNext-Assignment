"""Pure preparer and checker roles for handoff policy."""

from __future__ import annotations

from .types import BriefDraft, CheckIssue, CheckResult, OpportunitySnapshot


def prepare_brief(snapshot: OpportunitySnapshot) -> BriefDraft:
    if snapshot.fair_code is None or snapshot.client_budget_eur is None:
        proposed_next_step = "Ask sales to confirm the fair edition and client budget before technical intake."
    elif (
        snapshot.requested_height_m is not None
        and snapshot.max_stand_height_m is not None
        and snapshot.requested_height_m > snapshot.max_stand_height_m
    ):
        proposed_next_step = "Resolve the requested-height conflict with the customer before technical work begins."
    elif snapshot.stand_area_sqm is None or snapshot.requested_height_m is None:
        proposed_next_step = "Send an intake-only heads-up to technical and follow up for the missing dimensions."
    else:
        proposed_next_step = "Continue with the checked brief to technical."
    return BriefDraft.from_snapshot(snapshot, proposed_next_step=proposed_next_step)


def check_brief(draft: BriefDraft, snapshot: OpportunitySnapshot) -> CheckResult:
    issues: list[CheckIssue] = []
    if snapshot.fair_code is None:
        issues.append(CheckIssue("MISSING_FAIR", "Fair edition is required."))
    if snapshot.client_budget_eur is None:
        issues.append(CheckIssue("MISSING_BUDGET", "Client budget is required."))
    if snapshot.stand_area_sqm is None:
        issues.append(CheckIssue("MISSING_AREA", "Stand area is required."))
    if snapshot.requested_height_m is None:
        issues.append(CheckIssue("MISSING_HEIGHT", "Requested stand height is required."))
    if (
        snapshot.requested_height_m is not None
        and snapshot.max_stand_height_m is not None
        and snapshot.requested_height_m > snapshot.max_stand_height_m
    ):
        issues.append(
            CheckIssue(
                "HEIGHT_EXCEEDS_LIMIT",
                "Requested height exceeds the fair edition limit.",
                {
                    "requested_height_m": snapshot.requested_height_m,
                    "max_stand_height_m": snapshot.max_stand_height_m,
                },
            )
        )
    blocking_codes = {
        "MISSING_FAIR",
        "MISSING_BUDGET",
        "MISSING_AREA",
        "MISSING_HEIGHT",
        "HEIGHT_EXCEEDS_LIMIT",
    }
    proposal_is_safe = not (
        draft.proposed_next_step == "Continue with the checked brief to technical."
        and {issue.code for issue in issues} & blocking_codes
    )
    if not proposal_is_safe:
        issues.append(
            CheckIssue(
                "UNSAFE_PROPOSED_STEP",
                "The proposed next step continues technical work despite unresolved intake facts.",
            )
        )
    return CheckResult(issues=issues, proposal_is_safe=proposal_is_safe)
