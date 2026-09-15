from django.db import transaction

from .forms import EDITABLE_FIELDS
from .models import Opportunity


@transaction.atomic
def update_opportunity(opportunity: Opportunity, cleaned_data: dict) -> Opportunity:
    """Persist only the fields sales may edit in the opportunity workspace."""
    for field_name in EDITABLE_FIELDS:
        setattr(opportunity, field_name, cleaned_data[field_name])
    opportunity.full_clean()
    opportunity.save(update_fields=EDITABLE_FIELDS)
    return opportunity
