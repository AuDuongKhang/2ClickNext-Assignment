from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
import pytest

from crm.models import Company, Contact
from crm.selectors import search_crm


@pytest.mark.django_db
def test_search_finds_contact_and_returns_company_context(client, contact):
    contact.email = "ada@example.test"
    contact.save(update_fields=["email"])

    response = client.get("/search/", {"q": contact.email})

    assert response.status_code == 200
    assert contact.full_name in response.content.decode()
    assert contact.company.name in response.content.decode()


@pytest.mark.django_db
def test_search_returns_no_results_for_blank_query(client, company):
    response = client.get("/search/", {"q": "   "})

    assert response.status_code == 200
    assert response.context["company_results"] == []
    assert response.context["contact_results"] == []


@pytest.mark.django_db
def test_search_orders_exact_company_legacy_code_before_name_match(client):
    name_match = Company.objects.create(legacy_code="CO-OTHER", name="CO-EXACT Collective")
    exact_match = Company.objects.create(legacy_code="CO-EXACT", name="Aardvark Exhibitions")

    response = client.get("/search/", {"q": "CO-EXACT"})

    assert response.status_code == 200
    assert response.context["company_results"][0] == exact_match
    assert name_match in response.context["company_results"]


@pytest.mark.django_db
def test_search_uses_postgresql_trigram_similarity_operators_for_fuzzy_candidates():
    Company.objects.create(legacy_code="CO-FUZZY", name="Acme Exhibitions")

    with CaptureQueriesContext(connection) as queries:
        search_crm("Acme")

    search_queries = [query["sql"] for query in queries if "crm_company" in query["sql"]]
    assert any(" % " in query for query in search_queries)


@pytest.mark.django_db
def test_search_ranks_legacy_code_then_phone_then_fuzzy_contact_matches(client):
    legacy_match = Contact.objects.create(
        legacy_code="LEAD-001", company=Company.objects.create(legacy_code="CO-LEGACY", name="Legacy"),
        first_name="Zoe", last_name="Zulu",
    )
    phone_match = Contact.objects.create(
        legacy_code="AAA-PHONE", company=Company.objects.create(legacy_code="CO-PHONE", name="Phone"),
        first_name="Yara", last_name="Yellow", phone="001",
    )
    fuzzy_match = Contact.objects.create(
        legacy_code="ZZZ-FUZZY", company=Company.objects.create(legacy_code="CO-FUZZY", name="Fuzzy"),
        first_name="LEAD-001", last_name="Alpha",
    )

    response = client.get("/search/", {"q": "LEAD-001"})

    assert response.status_code == 200
    assert response.context["contact_results"][:3] == [legacy_match, phone_match, fuzzy_match]


@pytest.mark.django_db
def test_search_does_not_rank_blank_phone_as_a_match_for_text_queries(client):
    legacy_match = Contact.objects.create(
        legacy_code="Searchable", company=Company.objects.create(legacy_code="CO-LEGACY", name="Legacy"),
        first_name="Zoe", last_name="Zulu",
    )
    fuzzy_match = Contact.objects.create(
        legacy_code="AAA-FUZZY", company=Company.objects.create(legacy_code="CO-FUZZY", name="Fuzzy"),
        first_name="Searchable", last_name="Alpha",
    )

    response = client.get("/search/", {"q": "Searchable"})

    assert response.status_code == 200
    assert response.context["contact_results"][:2] == [legacy_match, fuzzy_match]


@pytest.mark.django_db
def test_search_matches_a_normalized_phone_number_and_persists_the_search_value(client, contact):
    contact.phone = "+44 (20) 7946-0958"
    contact.save(update_fields=["phone"])

    response = client.get("/search/", {"q": "44 20 7946 0958"})

    contact.refresh_from_db()
    assert response.status_code == 200
    assert response.context["contact_results"] == [contact]
    assert contact.phone_search == "442079460958"


@pytest.mark.django_db
def test_search_limits_each_result_type_to_twenty_five_and_avoids_contact_n_plus_one(client):
    for number in range(30):
        company = Company.objects.create(
            legacy_code=f"CO-{number}", name=f"Exhibitor {number} Searchable"
        )
        Contact.objects.create(
            legacy_code=f"CT-{number}",
            company=company,
            first_name="Searchable",
            last_name=str(number),
            email=f"searchable-{number}@example.test",
        )

    with CaptureQueriesContext(connection) as queries:
        response = client.get("/search/", {"q": "Searchable"})

    assert response.status_code == 200
    assert len(response.context["company_results"]) == 25
    assert len(response.context["contact_results"]) == 25
    assert len(queries) <= 3


@pytest.mark.django_db
def test_search_page_two_returns_later_matches_and_exposes_continuation_links(client):
    for number in range(27):
        company = Company.objects.create(
            legacy_code=f"CO-PAGE-{number:02d}", name=f"Paged Company {number:02d}"
        )
        Contact.objects.create(
            legacy_code=f"CT-PAGE-{number:02d}",
            company=company,
            first_name="Paged",
            last_name=f"Contact {number:02d}",
            email=f"paged-{number:02d}@example.test",
        )

    first_page = client.get(reverse("search"), {"q": "Paged"})
    second_page = client.get(reverse("search"), {"q": "Paged", "page": 2})

    assert first_page.context["has_next_companies"] is True
    assert first_page.context["has_next_contacts"] is True
    assert first_page.context["has_previous_companies"] is False
    assert first_page.context["has_previous_contacts"] is False
    assert any(item.legacy_code == "CO-PAGE-25" for item in second_page.context["company_results"])
    assert any(item.legacy_code == "CT-PAGE-25" for item in second_page.context["contact_results"])
    assert second_page.context["has_previous_companies"] is True
    assert second_page.context["has_previous_contacts"] is True
    assert second_page.context["has_next_companies"] is False
    assert second_page.context["has_next_contacts"] is False
    content = first_page.content.decode()
    assert f"{reverse('search')}?q=Paged&amp;page=2" in content
    assert f"{reverse('search')}?q=Paged&amp;page=1" in second_page.content.decode()
