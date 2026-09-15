from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from .forms import OpportunityForm
from .models import Opportunity
from .selectors import get_opportunity_workspace
from .services import update_opportunity


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
        },
    )


def opportunity_edit(request, legacy_code):
    try:
        workspace = get_opportunity_workspace(legacy_code)
    except Opportunity.DoesNotExist as error:
        raise Http404("Opportunity not found") from error

    opportunity = workspace.opportunity
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
        {"opportunity": opportunity, "form": form},
    )
