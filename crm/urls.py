from django.urls import path

from . import views


urlpatterns = [
    path("search/", views.search, name="search"),
    path("companies/<str:legacy_code>/", views.company_detail, name="company-detail"),
]
