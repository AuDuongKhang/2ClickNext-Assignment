from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from opportunities.models import Opportunity
from opportunities.selectors import get_opportunity

from .forms import ConversationForm, FollowUpForm
from .models import FollowUp
from .selectors import FOLLOW_UP_FILTERS, get_follow_up_inbox
from .services import complete_follow_up, record_conversation, schedule_follow_up


LOCAL_AUTHOR = "Sales user"


def _get_opportunity(legacy_code):
    try:
        return get_opportunity(legacy_code)
    except Opportunity.DoesNotExist as error:
        raise Http404("Opportunity not found") from error


def conversation_new(request, legacy_code):
    opportunity = _get_opportunity(legacy_code)
    if request.method == "POST":
        form = ConversationForm(request.POST)
        if form.is_valid():
            record_conversation(
                opportunity=opportunity,
                author=LOCAL_AUTHOR,
                **form.cleaned_data,
            )
            messages.success(request, "Conversation recorded.")
            return redirect("opportunity-detail", legacy_code=opportunity.legacy_code)
    else:
        form = ConversationForm()
    return render(request, "activities/conversation_form.html", {"form": form, "opportunity": opportunity})


def follow_up_new(request, legacy_code):
    opportunity = _get_opportunity(legacy_code)
    if request.method == "POST":
        form = FollowUpForm(request.POST)
        if form.is_valid():
            schedule_follow_up(
                company=opportunity.company,
                opportunity=opportunity,
                author=LOCAL_AUTHOR,
                **form.cleaned_data,
            )
            messages.success(request, "Follow-up scheduled.")
            return redirect("opportunity-detail", legacy_code=opportunity.legacy_code)
    else:
        form = FollowUpForm()
    return render(request, "activities/followup_form.html", {"form": form, "opportunity": opportunity})


def follow_up_list(request):
    selected_filter, follow_ups = get_follow_up_inbox(request.GET.get("filter"))
    return render(
        request,
        "activities/followup_list.html",
        {"follow_ups": follow_ups, "selected_filter": selected_filter, "filters": FOLLOW_UP_FILTERS},
    )


@require_POST
def follow_up_complete(request, pk):
    follow_up = get_object_or_404(FollowUp, pk=pk)
    complete_follow_up(follow_up)
    messages.success(request, "Follow-up completed.")
    return redirect("follow-up-list")
