from django.db import models

from crm.models import Company
from opportunities.models import Opportunity


class ActivityType(models.TextChoices):
    CALL = "call", "Call"
    EMAIL = "email", "Email"
    MEETING = "meeting", "Meeting"
    NOTE = "note", "Note"
    TASK = "task", "Task"


class Activity(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    company = models.ForeignKey(Company, on_delete=models.PROTECT, related_name="activities")
    opportunity = models.ForeignKey(
        Opportunity,
        on_delete=models.PROTECT,
        related_name="activities",
        null=True,
        blank=True,
    )
    activity_type = models.CharField(max_length=16, choices=ActivityType)
    occurred_at = models.DateTimeField()
    details = models.TextField()
    completed = models.BooleanField(null=True, blank=True)
    legacy_author = models.CharField(max_length=255, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["company", "occurred_at"]),
            models.Index(fields=["opportunity", "occurred_at"]),
        ]


class FollowUp(models.Model):
    opportunity = models.ForeignKey(Opportunity, on_delete=models.PROTECT, related_name="follow_ups")
    due_on = models.DateField()
    summary = models.TextField()
    created_at = models.DateTimeField()
    author = models.CharField(max_length=255)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["due_on", "completed_at"])]
