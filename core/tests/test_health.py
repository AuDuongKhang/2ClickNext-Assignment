import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_health_reports_web_and_database(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
