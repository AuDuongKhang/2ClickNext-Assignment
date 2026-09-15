from datetime import date
from decimal import Decimal

import pytest
from django.utils import timezone

from activities.models import FollowUp, FollowUpStatus
from crm.models import Company, Contact
from handoffs.models import HandoffRun


@pytest.mark.django_db
def test_opportunity_timeline_excludes_other_editions(
    client, opportunity, other_opportunity, activity_factory
):
    visible = activity_factory(opportunity=opportunity, details="Current edition call")
    activity_factory(opportunity=other_opportunity, details="Old agreement")

    response = client.get(f"/opportunities/{opportunity.legacy_code}/")

    content = response.content.decode()
    assert response.status_code == 200
    assert visible.details in content
    assert "Old agreement" not in content


@pytest.mark.django_db
def test_detail_excludes_company_followups_and_closed_followups(client, opportunity):
    FollowUp.objects.create(
        company=opportunity.company,
        opportunity=None,
        due_on=None,
        summary="Company-level follow-up",
        created_at=timezone.now(),
        author="sales.user",
    )
    FollowUp.objects.create(
        company=opportunity.company,
        opportunity=opportunity,
        due_on=date(2027, 1, 4),
        summary="Closed opportunity follow-up",
        created_at=timezone.now(),
        author="sales.user",
        status=FollowUpStatus.COMPLETED,
    )
    FollowUp.objects.create(
        company=opportunity.company,
        opportunity=opportunity,
        due_on=None,
        summary="Open opportunity follow-up",
        created_at=timezone.now(),
        author="sales.user",
    )

    response = client.get(f"/opportunities/{opportunity.legacy_code}/")

    content = response.content.decode()
    assert "Open opportunity follow-up" in content
    assert "Company-level follow-up" not in content
    assert "Closed opportunity follow-up" not in content


@pytest.mark.django_db
def test_detail_shows_only_current_opportunity_handoff_history(client, opportunity, other_opportunity):
    HandoffRun.objects.create(
        opportunity=opportunity,
        snapshot={},
        decision="approved",
        reason="Ready for build",
        policy_version="v1",
        status="completed",
    )
    HandoffRun.objects.create(
        opportunity=other_opportunity,
        snapshot={},
        decision="rejected",
        reason="Old opportunity",
        policy_version="v1",
        status="completed",
    )

    response = client.get(f"/opportunities/{opportunity.legacy_code}/")

    content = response.content.decode()
    assert "Ready for build" in content
    assert "Old opportunity" not in content


@pytest.mark.django_db
def test_edit_preserves_unknown_values_as_null(client, opportunity):
    response = client.post(
        f"/opportunities/{opportunity.legacy_code}/edit/",
        {
            "description": opportunity.description,
            "sales_stage": "qualified",
            "client_budget_eur": "",
            "stand_area_sqm": "80.00",
            "requested_height_m": "4.00",
            "brief_notes": "Reception and storage",
            "primary_contact": opportunity.primary_contact_id or "",
        },
    )

    assert response.status_code == 302
    opportunity.refresh_from_db()
    assert opportunity.client_budget_eur is None


@pytest.mark.django_db
def test_edit_updates_only_declared_fields_and_redirects_with_message(client, opportunity):
    opportunity.amount_eur = Decimal("15000.00")
    opportunity.save(update_fields=["amount_eur"])

    response = client.post(
        f"/opportunities/{opportunity.legacy_code}/edit/",
        {
            "description": "Updated reception stand",
            "sales_stage": "proposal",
            "client_budget_eur": "12000.00",
            "stand_area_sqm": "80.00",
            "requested_height_m": "4.00",
            "brief_notes": "Reception and storage",
            "primary_contact": opportunity.primary_contact_id,
            "amount_eur": "1.00",
            "fair_edition": "",
        },
        follow=True,
    )

    assert response.redirect_chain == [
        (f"/opportunities/{opportunity.legacy_code}/", 302)
    ]
    opportunity.refresh_from_db()
    assert opportunity.description == "Updated reception stand"
    assert opportunity.sales_stage == "proposal"
    assert opportunity.client_budget_eur == Decimal("12000.00")
    assert opportunity.stand_area_sqm == Decimal("80.00")
    assert opportunity.requested_height_m == Decimal("4.00")
    assert opportunity.brief_notes == "Reception and storage"
    assert opportunity.amount_eur == Decimal("15000.00")
    assert "Opportunity updated." in response.content.decode()


@pytest.mark.django_db
def test_edit_rejects_primary_contact_from_another_company(client, opportunity):
    other_company = Company.objects.create(legacy_code="CO2", name="Other Exhibitor")
    other_company_contact = Contact.objects.create(
        legacy_code="P2",
        company=other_company,
        first_name="Grace",
        last_name="Hopper",
    )

    response = client.post(
        f"/opportunities/{opportunity.legacy_code}/edit/",
        {
            "description": opportunity.description,
            "sales_stage": opportunity.sales_stage,
            "client_budget_eur": "",
            "stand_area_sqm": "",
            "requested_height_m": "",
            "brief_notes": "",
            "primary_contact": other_company_contact.pk,
        },
    )

    assert response.status_code == 200
    opportunity.refresh_from_db()
    assert opportunity.primary_contact_id != other_company_contact.pk
    assert "Select a valid choice" in response.content.decode()


@pytest.mark.django_db
def test_detail_shows_budget_and_height_constraint_warning_separately(client, opportunity):
    opportunity.amount_eur = Decimal("15000.00")
    opportunity.client_budget_eur = Decimal("12000.00")
    opportunity.requested_height_m = Decimal("6.00")
    opportunity.save()

    response = client.get(f"/opportunities/{opportunity.legacy_code}/")

    content = response.content.decode()
    assert "Opportunity value" in content
    assert "15,000.00" in content
    assert "Client budget" in content
    assert "12,000.00" in content
    assert "Requested height" in content
    assert "6.00" in content
    assert "Maximum stand height" in content
    assert "5.00" in content
    assert "Requested height exceeds the fair maximum." in content
