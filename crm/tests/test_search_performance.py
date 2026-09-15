"""PostgreSQL query-plan coverage for archive-scale CRM search data."""

import json
from datetime import date, datetime, timezone
from time import perf_counter

import pytest
from django.contrib.postgres.search import TrigramSimilarity
from django.db import connection
from django.db.models import Case, IntegerField, Q, Value, When
from django.db.models.functions import Greatest

from activities.models import Activity
from crm.models import Company, Contact, normalize_phone
from fairs.models import FairEdition
from opportunities.models import Opportunity
from crm.selectors import PAGE_SIZE, search_crm


pytestmark = pytest.mark.django_db(transaction=True)


COMPANY_COUNT = 50_000
CONTACT_COUNT = 100_000
OPPORTUNITY_COUNT = 75_000
ACTIVITY_COUNT = 200_000
BATCH_SIZE = 5_000


def _bulk_create(model, objects):
    for start in range(0, len(objects), BATCH_SIZE):
        model.objects.bulk_create(objects[start : start + BATCH_SIZE], batch_size=BATCH_SIZE)


def _plan_node_types(plan):
    yield plan["Node Type"]
    for child in plan.get("Plans", []):
        yield from _plan_node_types(child)


def _assert_index_plan(queryset, label):
    plan = json.loads(queryset.explain(format="JSON"))[0]["Plan"]
    node_types = list(_plan_node_types(plan))
    print(f"{label} plan nodes: {node_types}")
    assert "Seq Scan" not in node_types, f"{label} used a sequential scan: {node_types}"
    assert any("Index" in node_type for node_type in node_types), (
        f"{label} did not use an index node: {node_types}"
    )


def _time_application_search(query, label, expected_company_code=None, expected_contact_code=None):
    started_at = perf_counter()
    results = search_crm(query)
    elapsed_ms = (perf_counter() - started_at) * 1_000
    company_codes = {company.legacy_code for company in results.companies}
    contact_codes = {contact.legacy_code for contact in results.contacts}
    if expected_company_code is not None:
        assert expected_company_code in company_codes
    if expected_contact_code is not None:
        assert expected_contact_code in contact_codes
    print(
        f"{label}: {elapsed_ms:.2f} ms; "
        f"companies={len(results.companies)}, contacts={len(results.contacts)} "
        "(500 ms is a manual-review target)"
    )


def _production_search_querysets(query):
    """Mirror search_crm's result querysets for EXPLAIN without materializing them."""
    cleaned_query = query.strip()
    normalized_phone = normalize_phone(cleaned_query)
    page_slice = slice(0, PAGE_SIZE)

    company_queryset = (
        Company.objects.annotate(
            exact_match=Case(
                When(legacy_code__iexact=cleaned_query, then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            similarity=TrigramSimilarity("name", cleaned_query),
        )
        .filter(Q(legacy_code__iexact=cleaned_query) | Q(name__trigram_similar=cleaned_query))
        .order_by("exact_match", "-similarity", "name", "legacy_code")[page_slice]
    )

    contact_matches = Q(legacy_code__iexact=cleaned_query)
    contact_rank_cases = [When(legacy_code__iexact=cleaned_query, then=Value(0))]
    if normalized_phone:
        contact_matches |= Q(phone_search=normalized_phone)
        contact_rank_cases.append(When(phone_search=normalized_phone, then=Value(1)))
    fuzzy_contact_matches = (
        Q(first_name__trigram_similar=cleaned_query)
        | Q(last_name__trigram_similar=cleaned_query)
        | Q(email__trigram_similar=cleaned_query)
    )
    contact_queryset = (
        Contact.objects.select_related("company")
        .annotate(
            exact_match=Case(
                *contact_rank_cases,
                default=Value(2),
                output_field=IntegerField(),
            ),
            similarity=Greatest(
                TrigramSimilarity("first_name", cleaned_query),
                TrigramSimilarity("last_name", cleaned_query),
                TrigramSimilarity("email", cleaned_query),
            ),
        )
        .filter(contact_matches | fuzzy_contact_matches)
        .order_by("exact_match", "-similarity", "last_name", "first_name", "legacy_code")[page_slice]
    )
    return company_queryset, contact_queryset


def _create_archive_scale_fixture():
    _bulk_create(
        Company,
        [
            Company(
                legacy_code=f"PERF-COMPANY-{number:06d}",
                name=("Search Plan Company" if number == 0 else f"Vendor {number:06d}"),
            )
            for number in range(COMPANY_COUNT)
        ],
    )
    company_ids = list(Company.objects.order_by("legacy_code").values_list("id", flat=True))

    _bulk_create(
        Contact,
        [
            Contact(
                legacy_code=f"PERF-CONTACT-{number:06d}",
                company_id=company_ids[number % COMPANY_COUNT],
                first_name=("Search Plan Contact" if number == 0 else f"Person{number:06d}"),
                last_name="Record",
                email=(
                    "search-plan-contact@example.test"
                    if number == 0
                    else f"bulk-{number:06d}@example.invalid"
                ),
                phone=("+44 20 7946 0958" if number == 0 else f"+44 20 7000 {number:04d}"),
                phone_search=("442079460958" if number == 0 else f"44207000{number:04d}"),
            )
            for number in range(CONTACT_COUNT)
        ],
    )
    contact_ids = list(Contact.objects.order_by("legacy_code").values_list("id", flat=True))

    fair_edition = FairEdition.objects.create(
        legacy_code="PERF-FAIR-2027",
        fair_name="Performance Fair",
        city="Rome",
        venue="Test Hall",
        starts_on=date(2027, 5, 1),
        ends_on=date(2027, 5, 3),
    )
    _bulk_create(
        Opportunity,
        [
            Opportunity(
                legacy_code=f"PERF-OPPORTUNITY-{number:06d}",
                company_id=company_ids[number % COMPANY_COUNT],
                primary_contact_id=contact_ids[number % CONTACT_COUNT],
                fair_edition=fair_edition,
                description="Generated performance fixture",
                sales_stage="open",
            )
            for number in range(OPPORTUNITY_COUNT)
        ],
    )
    opportunity_ids = list(Opportunity.objects.order_by("legacy_code").values_list("id", flat=True))
    occurred_at = datetime(2027, 1, 1, tzinfo=timezone.utc)
    _bulk_create(
        Activity,
        [
            Activity(
                legacy_code=f"PERF-ACTIVITY-{number:06d}",
                company_id=company_ids[number % COMPANY_COUNT],
                opportunity_id=opportunity_ids[number % OPPORTUNITY_COUNT],
                activity_type="note",
                occurred_at=occurred_at,
                details="Generated performance fixture",
            )
            for number in range(ACTIVITY_COUNT)
        ],
    )
    with connection.cursor() as cursor:
        # Django renders __iexact as UPPER(column) = UPPER(value). The
        # matching expression indexes are created by the CRM migration.
        cursor.execute("ANALYZE crm_company")
        cursor.execute("ANALYZE crm_contact")
        cursor.execute("ANALYZE opportunities_opportunity")
        cursor.execute("ANALYZE activities_activity")


def test_archive_scale_searches_use_production_query_plans_and_timings():
    _create_archive_scale_fixture()

    searches = {
        "company-name": ("Search Plan Company", "PERF-COMPANY-000000", None),
        "contact-name": ("Search Plan Contact", None, "PERF-CONTACT-000000"),
        "email": ("search-plan-contact@example.test", None, "PERF-CONTACT-000000"),
        "phone": ("+44 20 7946 0958", None, "PERF-CONTACT-000000"),
        "legacy-code": ("perf-contact-000000", None, "PERF-CONTACT-000000"),
    }
    for label, (query, expected_company_code, expected_contact_code) in searches.items():
        company_queryset, contact_queryset = _production_search_querysets(query)
        _assert_index_plan(company_queryset, f"{label} company branch")
        _assert_index_plan(contact_queryset, f"{label} contact branch")
        _time_application_search(query, label, expected_company_code, expected_contact_code)
