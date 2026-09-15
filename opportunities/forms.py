from decimal import Decimal

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


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    english_value = f"{Decimal(value):,.2f}"
    return english_value.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


class EuropeanDecimalField(forms.DecimalField):
    """Parse and display decimal values with a comma decimal separator."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", forms.TextInput(attrs={"inputmode": "decimal"}))
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        if isinstance(value, str):
            return value
        return format_decimal(value) if value is not None else value

    def to_python(self, value):
        if isinstance(value, str):
            value = value.strip().replace("\u00a0", "").replace(" ", "")
            if "," in value:
                value = value.replace(".", "").replace(",", ".")
        return super().to_python(value)


class OpportunityForm(forms.ModelForm):
    client_budget_eur = EuropeanDecimalField(
        max_digits=12, decimal_places=2, required=False
    )
    stand_area_sqm = EuropeanDecimalField(
        max_digits=12, decimal_places=2, required=False
    )
    requested_height_m = EuropeanDecimalField(
        max_digits=5, decimal_places=2, required=False
    )

    class Meta:
        model = Opportunity
        fields = EDITABLE_FIELDS

    def __init__(self, *args, opportunity: Opportunity, **kwargs):
        super().__init__(*args, instance=opportunity, **kwargs)
        self.fields["primary_contact"].queryset = Contact.objects.filter(
            company=opportunity.company
        ).order_by("last_name", "first_name", "legacy_code")
