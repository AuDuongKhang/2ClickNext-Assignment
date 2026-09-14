from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from fairs.models import FairEdition


@pytest.mark.django_db
def test_fair_end_cannot_precede_start():
    fair = FairEdition(
        legacy_code="BAD-2027",
        fair_name="Bad dates",
        city="Rome",
        venue="Hall",
        starts_on=date(2027, 5, 2),
        ends_on=date(2027, 5, 1),
        max_stand_height_m=Decimal("5.00"),
    )

    with pytest.raises(ValidationError):
        fair.full_clean()
