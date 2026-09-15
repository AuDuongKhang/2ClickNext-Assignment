from django.db import connection
from django.test.utils import CaptureQueriesContext
import pytest
from django.utils import timezone

from activities.models import Activity
from crm.models import Contact
from opportunities.models import Opportunity


@pytest.mark.django_db
def test_company_detail_groups_opportunities_by_exact_fair_edition(client, company, opportunities):
    response = client.get(f"/companies/{company.legacy_code}/")

    assert response.status_code == 200
    assert response.context["company"] == company
    assert len(response.context["edition_groups"]) == 2


@pytest.mark.django_db
def test_company_detail_contains_company_activity_but_labels_opportunity_activity(
    client, company, opportunity, activity_factory
):
    company_note = Activity.objects.create(
        legacy_code="AC-COMPANY-NOTE",
        company=company,
        opportunity=None,
        activity_type="note",
        occurred_at=timezone.now(),
        details="Company-wide note",
        author="legacy-user",
    )
    opportunity_activity = activity_factory(opportunity=opportunity, details="Edition-specific call")

    response = client.get(f"/companies/{company.legacy_code}/")

    assert company_note in response.context["company_activities"]
    assert opportunity_activity in response.context["opportunity_activities"]
    activity_entry = response.context["opportunity_activities"][0]
    assert activity_entry.opportunity == opportunity
    assert activity_entry.fair_edition == opportunity.fair_edition


@pytest.mark.django_db
def test_company_detail_does_not_leak_another_companies_opportunity_activity(
    client, company, fair_edition, activity_factory
):
    other_company = company.__class__.objects.create(legacy_code="CO-OTHER", name="Other Exhibitor")
    other_opportunity = Opportunity.objects.create(
        legacy_code="OP-OTHER",
        company=other_company,
        fair_edition=fair_edition,
        description="Other company stand",
        sales_stage="open",
    )
    other_activity = activity_factory(other_opportunity, "Private other-company call")

    response = client.get(f"/companies/{company.legacy_code}/")

    assert other_activity not in response.context["opportunity_activities"]


@pytest.mark.django_db
def test_company_detail_uses_fixed_query_count_for_many_opportunities(client, company, fair_edition):
    for number in range(30):
        primary_contact = Contact.objects.create(
            legacy_code=f"CT-{number}",
            company=company,
            first_name="Primary",
            last_name=str(number),
        )
        opportunity = Opportunity.objects.create(
            legacy_code=f"OP-{number}",
            company=company,
            fair_edition=fair_edition,
            primary_contact=primary_contact,
            description=f"Stand {number}",
            sales_stage="open",
        )
        Activity.objects.create(
            legacy_code=f"AC-{number}",
            company=company,
            opportunity=opportunity,
            activity_type="call",
            occurred_at=timezone.now(),
            details=f"Call {number}",
            author="legacy-user",
        )

    with CaptureQueriesContext(connection) as queries:
        response = client.get(f"/companies/{company.legacy_code}/")

    assert response.status_code == 200
    assert len(response.context["opportunity_activities"]) == 30
    assert response.context["edition_groups"][0].opportunities[0].primary_contact.full_name
    assert len(queries) <= 6
