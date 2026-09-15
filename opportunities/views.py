from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from .forms import OpportunityForm, format_decimal
from .models import Opportunity
from .selectors import get_opportunity, get_opportunity_workspace
from .services import update_opportunity


def _decimal_displays(opportunity):
    return {
        "amount_eur": format_decimal(opportunity.amount_eur),
        "client_budget_eur": format_decimal(opportunity.client_budget_eur),
        "stand_area_sqm": format_decimal(opportunity.stand_area_sqm),
        "requested_height_m": format_decimal(opportunity.requested_height_m),
        "max_stand_height_m": format_decimal(opportunity.fair_edition.max_stand_height_m),
    }


def opportunity_detail(request, legacy_code):
    try:
        workspace = get_opportunity_workspace(legacy_code)
    except Opportunity.DoesNotExist as error:
        raise Http404("Opportunity not found") from error
    return render(
        request,
        "opportunities/detail.html",
        {
            "opportunity": workspace.opportunity,
            "activities": workspace.activities,
            "open_follow_ups": workspace.open_follow_ups,
            "handoff_runs": workspace.handoff_runs,
            "height_conflict": workspace.requested_height_exceeds_maximum,
            "decimal_displays": _decimal_displays(workspace.opportunity),
        },
    )


def opportunity_edit(request, legacy_code):
    try:
        opportunity = get_opportunity(legacy_code)
    except Opportunity.DoesNotExist as error:
        raise Http404("Opportunity not found") from error

    if request.method == "POST":
        form = OpportunityForm(request.POST, opportunity=opportunity)
        if form.is_valid():
            update_opportunity(opportunity, form.cleaned_data)
            messages.success(request, "Opportunity updated.")
            return redirect("opportunity-detail", legacy_code=opportunity.legacy_code)
    else:
        form = OpportunityForm(opportunity=opportunity)

    return render(
        request,
        "opportunities/edit.html",
        {
            "opportunity": opportunity,
            "form": form,
            "decimal_displays": _decimal_displays(opportunity),
        },
    )
