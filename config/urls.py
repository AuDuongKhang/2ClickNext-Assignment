from django.urls import include, path

from core.views import health


urlpatterns = [
    path("health/", health, name="health"),
    path("", include("core.urls")),
    path("", include("crm.urls")),
    path("", include("opportunities.urls")),
    path("", include("activities.urls")),
    path("", include("handoffs.urls")),
]
