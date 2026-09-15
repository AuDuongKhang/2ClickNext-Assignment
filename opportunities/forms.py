from django import forms

from crm.models import Contact

from .models import Opportunity


EDITABLE_FIELDS = (
    "description",
    "sales_stage",
    "primary_contact",
    "client_budget_eur",
    "stand_area_sqm",
    "requested_height_m",
    "brief_notes",
)


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = EDITABLE_FIELDS

    def __init__(self, *args, opportunity: Opportunity, **kwargs):
        super().__init__(*args, instance=opportunity, **kwargs)
        self.fields["primary_contact"].queryset = Contact.objects.filter(
            company=opportunity.company
        ).order_by("last_name", "first_name", "legacy_code")
