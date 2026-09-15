"""Coordinator policy for checked handoff briefs."""

from .types import BriefDraft, CheckResult, HandoffDecision


POLICY_VERSION = "2026-09-14.1"


def decide_handoff(draft: BriefDraft, check: CheckResult) -> HandoffDecision:
    codes = {issue.code for issue in check.issues}
    if not check.proposal_is_safe:
        return HandoffDecision("blocked_conflict", "blocked", "The proposed next step is not safe for the checked facts.", False, "none")
    if codes & {"MISSING_FAIR", "MISSING_BUDGET"}:
        return HandoffDecision("stop_insufficient", "blocked", "Fair and client budget are required before intake.", False, "none")
    if "HEIGHT_EXCEEDS_LIMIT" in codes:
        return HandoffDecision("blocked_conflict", "blocked", "Requested height exceeds the fair edition limit.", False, "none")
    if "UNKNOWN_FAIR_HEIGHT_LIMIT" in codes:
        return HandoffDecision(
            "early_intake",
            "early_intake",
            "Technical may review context but must wait for the fair maximum stand height.",
            True,
            "intake_only",
        )
    if codes & {"MISSING_AREA", "MISSING_HEIGHT"}:
        return HandoffDecision("early_intake", "early_intake", "Technical may review context but must wait for missing dimensions.", True, "intake_only")
    return HandoffDecision("ready_for_technical", "ready", "The checked brief contains all required technical intake values.", True, "technical_work")
