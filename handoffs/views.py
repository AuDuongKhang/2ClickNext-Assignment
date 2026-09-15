from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from opportunities.models import Opportunity
from opportunities.selectors import get_opportunity

from .models import HandoffRun
from .selectors import get_handoff_run
from .services import run_handoff


@require_POST
def handoff_run(request, legacy_code):
    try:
        opportunity = get_opportunity(legacy_code)
    except Opportunity.DoesNotExist as error:
        raise Http404("Opportunity not found") from error

    run = run_handoff(opportunity)
    if run.status == "completed":
        messages.success(request, "Handoff run recorded.")
    else:
        messages.error(request, "Handoff run failed safely; review the run detail.")
    return redirect("handoff-run-detail", pk=run.pk)


def handoff_run_detail(request, pk):
    try:
        run = get_handoff_run(pk)
    except HandoffRun.DoesNotExist as error:
        raise Http404("Handoff run not found") from error
    return render(request, "handoffs/run_detail.html", {"run": run})
