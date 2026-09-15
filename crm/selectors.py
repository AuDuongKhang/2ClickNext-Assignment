from collections import OrderedDict
from dataclasses import dataclass

from django.contrib.postgres.lookups import TrigramSimilar
from django.contrib.postgres.search import TrigramSimilarity
from django.db.models import Case, IntegerField, Prefetch, Q, Value, When
from django.db.models.functions import Greatest

from activities.models import Activity
from opportunities.models import Opportunity

from .models import Company, Contact, normalize_phone


PAGE_SIZE = 25


@dataclass(frozen=True)
class SearchResults:
    query: str
    page: int
    companies: list[Company]
    contacts: list[Contact]


@dataclass(frozen=True)
class EditionGroup:
    fair_edition: object
    opportunities: list[Opportunity]


@dataclass(frozen=True)
class CompanyWorkspace:
    company: Company
    edition_groups: list[EditionGroup]
    company_activities: list[Activity]
    opportunity_activities: list[Activity]


def _page_slice(page: int) -> slice:
    page = max(page, 1)
    start = (page - 1) * PAGE_SIZE
    return slice(start, start + PAGE_SIZE)


def search_crm(query: str, page: int = 1) -> SearchResults:
    """Return bounded company and contact matches for one CRM search page."""
    cleaned_query = query.strip()
    page = max(page, 1)
    if not cleaned_query:
        return SearchResults(query="", page=page, companies=[], contacts=[])

    page_slice = _page_slice(page)
    normalized_phone = normalize_phone(cleaned_query)
    companies = list(
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
    contacts = list(
        Contact.objects.select_related("company").annotate(
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
    return SearchResults(query=cleaned_query, page=page, companies=companies, contacts=contacts)


def get_company_workspace(legacy_code: str) -> CompanyWorkspace:
    """Load one company workspace in a fixed number of queries."""
    company = (
        Company.objects.prefetch_related(
            "contacts",
            Prefetch(
                "opportunities",
                queryset=Opportunity.objects.select_related("primary_contact", "fair_edition"),
            ),
        )
        .filter(legacy_code=legacy_code)
        .first()
    )
    if company is None:
        raise Company.DoesNotExist

    opportunities = sorted(
        company.opportunities.all(),
        key=lambda opportunity: (
            opportunity.fair_edition.starts_on,
            opportunity.fair_edition.legacy_code,
            opportunity.legacy_code,
        ),
    )
    grouped_opportunities: OrderedDict[int, EditionGroup] = OrderedDict()
    for opportunity in opportunities:
        group = grouped_opportunities.get(opportunity.fair_edition_id)
        if group is None:
            grouped_opportunities[opportunity.fair_edition_id] = EditionGroup(
                fair_edition=opportunity.fair_edition, opportunities=[opportunity]
            )
        else:
            group.opportunities.append(opportunity)

    company_activities = list(
        Activity.objects.filter(company=company, opportunity__isnull=True).order_by("-occurred_at", "-pk")
    )
    opportunity_activities = list(
        Activity.objects.filter(company=company, opportunity__isnull=False)
        .select_related("opportunity__fair_edition")
        .order_by("-occurred_at", "-pk")
    )
    for activity in opportunity_activities:
        activity.fair_edition = activity.opportunity.fair_edition

    return CompanyWorkspace(
        company=company,
        edition_groups=list(grouped_opportunities.values()),
        company_activities=company_activities,
        opportunity_activities=opportunity_activities,
    )
