from dataclasses import asdict, dataclass
from decimal import Decimal

from django.db import models

from opportunities.models import Opportunity


class TechnicalReadiness(models.TextChoices):
    NOT_REQUESTED = "not_requested", "Not requested"
    EARLY_INTAKE = "early_intake", "Early intake"
    BLOCKED = "blocked", "Blocked"
    READY = "ready", "Ready"


@dataclass(frozen=True)
class OpportunitySnapshot:
    fair_code: str | None
    client_budget_eur: Decimal | None
    stand_area_sqm: Decimal | None
    requested_height_m: Decimal | None
    max_stand_height_m: Decimal | None

    def as_dict(self):
        return {key: str(value) if isinstance(value, Decimal) else value for key, value in asdict(self).items()}


class HandoffRun(models.Model):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="handoff_runs")
    snapshot = models.JSONField()
    preparer_output = models.TextField(blank=True)
    reviewer_output = models.TextField(blank=True)
    decision = models.CharField(max_length=64)
    reason = models.TextField()
    policy_version = models.CharField(max_length=64)
    status = models.CharField(max_length=32)
    technical_readiness = models.CharField(
        max_length=32, choices=TechnicalReadiness, default=TechnicalReadiness.NOT_REQUESTED
    )
    error_type = models.CharField(max_length=128, null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["opportunity", "created_at"])]
