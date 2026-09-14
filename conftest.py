from datetime import date, datetime
from decimal import Decimal

import pytest
from django.utils import timezone

from activities.models import Activity, FollowUp
from crm.models import Company, Contact
from fairs.models import FairEdition
from handoffs.models import OpportunitySnapshot
from opportunities.models import Opportunity


@pytest.fixture
def company():
    return Company.objects.create(legacy_code="CO1", name="Example Exhibitor")


@pytest.fixture
def contact(company):
    return Contact.objects.create(
        legacy_code="P1", company=company, first_name="Ada", last_name="Lovelace"
    )


@pytest.fixture
def fair_edition():
    return FairEdition.objects.create(
        legacy_code="FAIR-2027",
        fair_name="Example Fair",
        city="Rome",
        venue="Main Hall",
        starts_on=date(2027, 5, 1),
        ends_on=date(2027, 5, 3),
        max_stand_height_m=Decimal("5.00"),
    )


@pytest.fixture
def opportunity(company, contact, fair_edition):
    return Opportunity.objects.create(
        legacy_code="OP1",
        company=company,
        primary_contact=contact,
        fair_edition=fair_edition,
        description="Launch stand",
        sales_stage="open",
    )


@pytest.fixture
def other_opportunity(company, fair_edition):
    other_edition = FairEdition.objects.create(
        legacy_code="FAIR-2028",
        fair_name=fair_edition.fair_name,
        city=fair_edition.city,
        venue=fair_edition.venue,
        starts_on=date(2028, 5, 1),
        ends_on=date(2028, 5, 3),
        max_stand_height_m=Decimal("5.00"),
    )
    return Opportunity.objects.create(
        legacy_code="OP2",
        company=company,
        fair_edition=other_edition,
        description="Next edition stand",
        sales_stage="open",
    )


@pytest.fixture
def opportunities(opportunity, other_opportunity):
    return opportunity, other_opportunity


@pytest.fixture
def activity_factory():
    def create(opportunity: Opportunity, details: str) -> Activity:
        return Activity.objects.create(
            legacy_code="AC-" + str(Activity.objects.count() + 1),
            company=opportunity.company,
            opportunity=opportunity,
            activity_type="call",
            occurred_at=timezone.make_aware(datetime(2027, 1, 1, 9, 0)),
            details=details,
            legacy_author="archive.user",
        )

    return create


@pytest.fixture
def follow_up_factory(opportunity):
    def create(due_on: date, summary: str) -> FollowUp:
        return FollowUp.objects.create(
            company=opportunity.company,
            opportunity=opportunity,
            due_on=due_on,
            summary=summary,
            created_at=timezone.now(),
            author="sales.user",
        )

    return create


@pytest.fixture
def snapshot_factory():
    def create(
        fair_code: str | None,
        budget: Decimal | None,
        area: Decimal | None,
        height: Decimal | None,
        maximum: Decimal | None,
    ) -> OpportunitySnapshot:
        return OpportunitySnapshot(
            fair_code=fair_code,
            client_budget_eur=budget,
            stand_area_sqm=area,
            requested_height_m=height,
            max_stand_height_m=maximum,
        )

    return create
