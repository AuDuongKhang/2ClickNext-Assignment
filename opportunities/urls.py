from django.urls import path

from . import views


urlpatterns = [
    path("opportunities/<str:legacy_code>/", views.opportunity_detail, name="opportunity-detail"),
    path("opportunities/<str:legacy_code>/edit/", views.opportunity_edit, name="opportunity-edit"),
]
