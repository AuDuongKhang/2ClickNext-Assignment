"""Immutable, JSON-safe contracts for deterministic handoff policy."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import TypeAlias


JsonValue: TypeAlias = str | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def _json_safe(value: object) -> JsonValue:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


@dataclass(frozen=True)
class OpportunitySnapshot:
    fair_code: str | None
    client_budget_eur: Decimal | None
    stand_area_sqm: Decimal | None
    requested_height_m: Decimal | None
    max_stand_height_m: Decimal | None
    commercial_context: dict[str, JsonValue] = field(default_factory=dict)
    customer_requirements: dict[str, JsonValue] = field(default_factory=dict)
    recent_interactions: list[dict[str, JsonValue]] = field(default_factory=list)
    open_follow_ups: list[dict[str, JsonValue]] = field(default_factory=list)

    def to_dict(self) -> dict[str, JsonValue]:
        return _json_safe(
            {
                "fair_code": self.fair_code,
                "client_budget_eur": self.client_budget_eur,
                "stand_area_sqm": self.stand_area_sqm,
                "requested_height_m": self.requested_height_m,
                "max_stand_height_m": self.max_stand_height_m,
                "commercial_context": self.commercial_context,
                "customer_requirements": self.customer_requirements,
                "recent_interactions": self.recent_interactions,
                "open_follow_ups": self.open_follow_ups,
            }
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class BriefDraft:
    snapshot: OpportunitySnapshot
    fair_code: str | None
    client_budget_eur: Decimal | None
    stand_area_sqm: Decimal | None
    requested_height_m: Decimal | None
    max_stand_height_m: Decimal | None
    commercial_context: dict[str, JsonValue]
    customer_requirements: dict[str, JsonValue]
    recent_interactions: list[dict[str, JsonValue]]
    open_follow_ups: list[dict[str, JsonValue]]
    open_questions: list[str]
    proposed_next_step: str

    @classmethod
    def from_snapshot(cls, snapshot: OpportunitySnapshot, *, proposed_next_step: str) -> "BriefDraft":
        open_questions = [
            question
            for value, question in (
                (snapshot.stand_area_sqm, "stand area"),
                (snapshot.requested_height_m, "requested height"),
                (snapshot.client_budget_eur, "client budget"),
                (snapshot.fair_code, "fair edition"),
            )
            if value is None
        ]
        return cls(
            snapshot=snapshot,
            fair_code=snapshot.fair_code,
            client_budget_eur=snapshot.client_budget_eur,
            stand_area_sqm=snapshot.stand_area_sqm,
            requested_height_m=snapshot.requested_height_m,
            max_stand_height_m=snapshot.max_stand_height_m,
            commercial_context=snapshot.commercial_context,
            customer_requirements=snapshot.customer_requirements,
            recent_interactions=snapshot.recent_interactions,
            open_follow_ups=snapshot.open_follow_ups,
            open_questions=open_questions,
            proposed_next_step=proposed_next_step,
        )

    def to_dict(self) -> dict[str, JsonValue]:
        return _json_safe(
            {
                "snapshot": self.snapshot.to_dict(),
                "fair_code": self.fair_code,
                "client_budget_eur": self.client_budget_eur,
                "stand_area_sqm": self.stand_area_sqm,
                "requested_height_m": self.requested_height_m,
                "max_stand_height_m": self.max_stand_height_m,
                "commercial_context": self.commercial_context,
                "customer_requirements": self.customer_requirements,
                "recent_interactions": self.recent_interactions,
                "open_follow_ups": self.open_follow_ups,
                "open_questions": self.open_questions,
                "proposed_next_step": self.proposed_next_step,
            }
        )  # type: ignore[return-value]


@dataclass(frozen=True)
class CheckIssue:
    code: str
    reason: str
    evidence: dict[str, JsonValue] = field(default_factory=dict)

    def to_dict(self) -> dict[str, JsonValue]:
        return _json_safe({"code": self.code, "reason": self.reason, "evidence": self.evidence})  # type: ignore[return-value]


@dataclass(frozen=True)
class CheckResult:
    issues: list[CheckIssue]
    proposal_is_safe: bool

    def to_dict(self) -> dict[str, JsonValue]:
        return {"issues": [issue.to_dict() for issue in self.issues], "proposal_is_safe": self.proposal_is_safe}


@dataclass(frozen=True)
class HandoffDecision:
    code: str
    technical_readiness: str
    reason: str
    should_continue: bool
    allowed_scope: str

    def to_dict(self) -> dict[str, JsonValue]:
        return {
            "code": self.code,
            "technical_readiness": self.technical_readiness,
            "reason": self.reason,
            "should_continue": self.should_continue,
            "allowed_scope": self.allowed_scope,
        }
