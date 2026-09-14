from django.db import models
from django.db.models import F, Q


class FairEdition(models.Model):
    legacy_code = models.CharField(max_length=64, unique=True)
    fair_name = models.CharField(max_length=255)
    city = models.CharField(max_length=128)
    venue = models.CharField(max_length=255)
    starts_on = models.DateField()
    ends_on = models.DateField()
    max_stand_height_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_on__gte=F("starts_on")),
                name="fair_edition_end_not_before_start",
            ),
            models.CheckConstraint(
                condition=Q(max_stand_height_m__isnull=True) | Q(max_stand_height_m__gte=0),
                name="fair_edition_height_non_negative",
            ),
        ]
        indexes = [models.Index(fields=["fair_name", "starts_on"])]

    def __str__(self):
        return self.legacy_code
