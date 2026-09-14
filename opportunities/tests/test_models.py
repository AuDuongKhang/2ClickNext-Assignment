from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from crm.models import Company, Contact
from opportunities.models import Opportunity


@pytest.mark.django_db
def test_primary_contact_must_belong_to_opportunity_company(fair_edition):
    first = Company.objects.create(legacy_code="CO1", name="First")
    second = Company.objects.create(legacy_code="CO2", name="Second")
    contact = Contact.objects.create(
        legacy_code="P2", company=second, first_name="A", last_name="B"
    )
    opportunity = Opportunity(
        legacy_code="OP1",
        company=first,
        primary_contact=contact,
        fair_edition=fair_edition,
        description="Stand",
        sales_stage="open",
    )

    with pytest.raises(ValidationError, match="Primary contact must belong"):
        opportunity.full_clean()


@pytest.mark.django_db
def test_unknown_opportunity_numbers_remain_null(company, fair_edition):
    opportunity = Opportunity.objects.create(
        legacy_code="OP-NULLS",
        company=company,
        fair_edition=fair_edition,
        description="Unknown dimensions",
        sales_stage="open",
    )

    assert opportunity.client_budget_eur is None
    assert opportunity.stand_area_sqm is None
    assert opportunity.requested_height_m is None


@pytest.mark.django_db
def test_requested_height_above_fair_limit_is_retained(company, fair_edition):
    opportunity = Opportunity(
        legacy_code="OP-CONFLICT",
        company=company,
        fair_edition=fair_edition,
        description="Tall stand",
        sales_stage="open",
        requested_height_m=Decimal("6.00"),
    )

    opportunity.full_clean()


@pytest.mark.django_db
def test_raw_legacy_status_is_preserved_separately_from_sales_stage(company, fair_edition):
    opportunity = Opportunity.objects.create(
        legacy_code="OP-RAW-STATUS",
        company=company,
        fair_edition=fair_edition,
        description="Legacy status import",
        raw_legacy_status=" Open ",
        sales_stage="open",
    )

    assert opportunity.raw_legacy_status == " Open "
    assert opportunity.sales_stage == "open"
