from django.urls import path

from . import views


urlpatterns = [
    path("opportunities/<str:legacy_code>/conversations/new/", views.conversation_new, name="conversation-new"),
    path("opportunities/<str:legacy_code>/follow-ups/new/", views.follow_up_new, name="follow-up-new"),
    path("follow-ups/", views.follow_up_list, name="follow-up-list"),
    path("follow-ups/<int:pk>/complete/", views.follow_up_complete, name="follow-up-complete"),
]
