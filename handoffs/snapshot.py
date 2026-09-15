"""Build pure handoff snapshots from an opportunity and its scoped relations."""

from __future__ import annotations

from typing import Iterable

from .types import OpportunitySnapshot, _json_safe


RECENT_ACTIVITY_LIMIT = 50


def _items(related: object) -> Iterable[object]:
    all_items = getattr(related, "all", None)
    return all_items() if callable(all_items) else related  # type: ignore[return-value]


def _recent_activities(opportunity: object) -> Iterable[object]:
    related = getattr(opportunity, "activities", ())
    all_items = getattr(related, "all", None)
    if callable(all_items):
        items = all_items()
        order_by = getattr(items, "order_by", None)
        if callable(order_by):
            return order_by("-occurred_at", "-pk")[:RECENT_ACTIVITY_LIMIT]
    else:
        items = related
    return sorted(
        (activity for activity in items if _belongs_to(opportunity, activity)),
        key=lambda activity: (
            getattr(activity, "occurred_at", None),
            getattr(activity, "pk", 0) or 0,
        ),
        reverse=True,
    )[:RECENT_ACTIVITY_LIMIT]


def _belongs_to(opportunity: object, record: object) -> bool:
    record_opportunity = getattr(record, "opportunity", None)
    opportunity_id = getattr(opportunity, "pk", None)
    record_opportunity_id = getattr(record, "opportunity_id", None)
    if opportunity_id is not None and record_opportunity_id is not None:
        return opportunity_id == record_opportunity_id
    return record_opportunity is opportunity


def build_snapshot(opportunity: object) -> OpportunitySnapshot:
    """Copy only one opportunity's commercial facts and related work into a value object."""
    fair_edition = getattr(opportunity, "fair_edition", None)
    activities = [
        {
            "activity_type": getattr(activity, "activity_type", ""),
            "occurred_at": getattr(activity, "occurred_at", None),
            "details": getattr(activity, "details", ""),
            "author": getattr(activity, "author", ""),
        }
        for activity in _recent_activities(opportunity)
        if _belongs_to(opportunity, activity)
    ]
    follow_ups = [
        {
            "due_on": getattr(follow_up, "due_on", None),
            "summary": getattr(follow_up, "summary", ""),
            "status": getattr(follow_up, "status", ""),
            "author": getattr(follow_up, "author", ""),
        }
        for follow_up in _items(getattr(opportunity, "follow_ups", ()))
        if _belongs_to(opportunity, follow_up) and getattr(follow_up, "status", None) == "open"
    ]
    company = getattr(opportunity, "company", None)
    return OpportunitySnapshot(
        fair_code=getattr(fair_edition, "legacy_code", None),
        client_budget_eur=getattr(opportunity, "client_budget_eur", None),
        stand_area_sqm=getattr(opportunity, "stand_area_sqm", None),
        requested_height_m=getattr(opportunity, "requested_height_m", None),
        max_stand_height_m=getattr(fair_edition, "max_stand_height_m", None),
        commercial_context={
            "company_code": getattr(company, "legacy_code", None),
            "company_name": getattr(company, "name", None),
        },
        customer_requirements={
            "description": getattr(opportunity, "description", ""),
            "brief_notes": getattr(opportunity, "brief_notes", ""),
        },
        recent_interactions=[_json_safe(activity) for activity in activities],  # type: ignore[list-item]
        open_follow_ups=[_json_safe(follow_up) for follow_up in follow_ups],  # type: ignore[list-item]
    )
