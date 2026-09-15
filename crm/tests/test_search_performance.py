"""Opt-in PostgreSQL query-plan coverage for archive-scale CRM search data."""

import json
import os
from datetime import date, datetime, timezone
from time import perf_counter

import pytest
from django.db import connection

from activities.models import Activity
from crm.models import Company, Contact
from fairs.models import FairEdition
from opportunities.models import Opportunity


RUN_PERFORMANCE_TESTS = os.environ.get("RUN_SEARCH_PERFORMANCE") == "1"

pytestmark = [
    pytest.mark.skipif(
        not RUN_PERFORMANCE_TESTS,
        reason="set RUN_SEARCH_PERFORMANCE=1 to generate the archive-scale performance fixtures",
    ),
    pytest.mark.django_db(transaction=True),
]


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
    assert "Seq Scan" not in node_types, f"{label} used a sequential scan: {node_types}"
    assert any("Index" in node_type for node_type in node_types), (
        f"{label} did not use an index node: {node_types}"
    )


def _time_search(queryset, label):
    started_at = perf_counter()
    list(queryset[:25])
    elapsed_ms = (perf_counter() - started_at) * 1_000
    print(f"{label}: {elapsed_ms:.2f} ms (500 ms is a manual-review target)")


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
        cursor.execute("ANALYZE crm_company")
        cursor.execute("ANALYZE crm_contact")
        cursor.execute("ANALYZE opportunities_opportunity")
        cursor.execute("ANALYZE activities_activity")


def test_archive_scale_searches_use_postgresql_indexes():
    _create_archive_scale_fixture()

    searches = {
        "company-name": Company.objects.filter(name__trigram_similar="Search Plan Company"),
        "contact-name": Contact.objects.filter(first_name__trigram_similar="Search Plan Contact"),
        "email": Contact.objects.filter(email__trigram_similar="search-plan-contact@example.test"),
        "phone": Contact.objects.filter(phone_search="442079460958"),
        "legacy-code": Contact.objects.filter(legacy_code="PERF-CONTACT-000000"),
    }
    for label, queryset in searches.items():
        _assert_index_plan(queryset, label)
        _time_search(queryset, label)
