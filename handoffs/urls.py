from django.urls import path

from . import views


urlpatterns = [
    path("opportunities/<str:legacy_code>/handoffs/", views.handoff_run, name="handoff-run"),
    path("handoffs/<int:pk>/", views.handoff_run_detail, name="handoff-run-detail"),
]
