from django.http import Http404
from django.shortcuts import render

from .models import Company
from .selectors import get_company_workspace, search_crm


def search(request):
    try:
        page = max(int(request.GET.get("page", "1")), 1)
    except ValueError:
        page = 1
    results = search_crm(request.GET.get("q", ""), page)
    return render(
        request,
        "crm/search_results.html",
        {
            "query": results.query,
            "page": results.page,
            "company_results": results.companies,
            "contact_results": results.contacts,
            "has_next": results.has_next,
            "has_previous": results.has_previous,
            "has_next_companies": results.has_next_companies,
            "has_previous_companies": results.has_previous_companies,
            "has_next_contacts": results.has_next_contacts,
            "has_previous_contacts": results.has_previous_contacts,
        },
    )


def company_detail(request, legacy_code):
    try:
        workspace = get_company_workspace(legacy_code)
    except Company.DoesNotExist as error:
        raise Http404("Company not found") from error
    return render(
        request,
        "crm/company_detail.html",
        {
            "company": workspace.company,
            "edition_groups": workspace.edition_groups,
            "company_activities": workspace.company_activities,
            "opportunity_activities": workspace.opportunity_activities,
        },
    )
