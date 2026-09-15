import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from handoffs.models import HandoffRun


@pytest.mark.django_db
def test_run_handoff_is_post_only(client, opportunity):
    """The action endpoint must reject a GET rather than creating an audit run."""
    url = reverse("handoff-run", args=[opportunity.legacy_code])

    response = client.get(url)

    assert response.status_code == 405
    assert not HandoffRun.objects.exists()


@pytest.mark.django_db
def test_post_run_handoff_redirects_to_run_detail_with_message(client, opportunity):
    """A completed action must use POST/redirect/GET and leave a success message."""
    response = client.post(reverse("handoff-run", args=[opportunity.legacy_code]))

    run = HandoffRun.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("handoff-run-detail", args=[run.pk])
    assert [str(message) for message in get_messages(response.wsgi_request)] == [
        "Handoff run recorded."
    ]


@pytest.mark.django_db
def test_opportunity_detail_exposes_csrf_protected_handoff_action(client, opportunity):
    """The opportunity page must offer the handoff action through a CSRF form."""
    response = client.get(reverse("opportunity-detail", args=[opportunity.legacy_code]))

    content = response.content.decode()
    assert f'action="{reverse("handoff-run", args=[opportunity.legacy_code])}"' in content
    assert 'method="post"' in content
    assert 'name="csrfmiddlewaretoken"' in content


@pytest.mark.django_db
def test_run_detail_shows_auditable_role_outputs_and_opportunity_link(client, opportunity):
    """The detail page must expose stored evidence and deterministic-role provenance."""
    run = HandoffRun.objects.create(
        opportunity=opportunity,
        snapshot={"fair_code": "FAIR-2027"},
        preparer_output='{"proposed_next_step": "Continue"}',
        reviewer_output='{"issues": []}',
        decision="ready_for_technical",
        reason="Checked intake is complete.",
        policy_version="2026-09-14.1",
        status="completed",
        technical_readiness="ready",
    )

    response = client.get(reverse("handoff-run-detail", args=[run.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Deterministic local stand-in — no model call" in content
    assert "FAIR-2027" in content
    assert "Continue" in content
    assert "ready_for_technical" in content
    assert "2026-09-14.1" in content
    assert reverse("opportunity-detail", args=[opportunity.legacy_code]) in content
