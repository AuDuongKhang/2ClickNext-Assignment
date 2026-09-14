from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from crm.models import Company, Contact
from fairs.models import FairEdition


class SalesStage(models.TextChoices):
    OPEN = "open", "Open"
    QUALIFIED = "qualified", "Qualified"
    PROPOSAL = "proposal", "Proposal"
    WON = "won", "Won"
    LOST = "lost", "Lost"


class Opportunity(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="opportunities")
    primary_contact = models.ForeignKey(
        Contact,
        on_delete=models.SET_NULL,
        related_name="primary_opportunities",
        null=True,
        blank=True,
    )
    fair_edition = models.ForeignKey(
        FairEdition, on_delete=models.PROTECT, related_name="opportunities"
    )
    description = models.TextField()
    amount_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    sales_stage = models.CharField(max_length=16, choices=SalesStage, default=SalesStage.OPEN)
    raw_legacy_status = models.CharField(max_length=64, blank=True)
    opened_on = models.DateField(null=True, blank=True)
    expected_close_on = models.DateField(null=True, blank=True)
    historical_campaign_code = models.CharField(max_length=128, blank=True)
    stand_area_sqm = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    client_budget_eur = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    requested_height_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    brief_notes = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_eur__isnull=True) | Q(amount_eur__gte=0),
                name="opportunity_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(stand_area_sqm__isnull=True) | Q(stand_area_sqm__gte=0),
                name="opportunity_area_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(client_budget_eur__isnull=True) | Q(client_budget_eur__gte=0),
                name="opportunity_budget_non_negative",
            ),
            models.CheckConstraint(
                condition=Q(requested_height_m__isnull=True) | Q(requested_height_m__gte=0),
                name="opportunity_height_non_negative",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "fair_edition"]),
            models.Index(fields=["sales_stage", "expected_close_on"]),
        ]

    def clean(self):
        super().clean()
        if self.primary_contact_id and self.primary_contact.company_id != self.company_id:
            raise ValidationError({"primary_contact": "Primary contact must belong to opportunity company."})

    def __str__(self):
        return self.legacy_code
