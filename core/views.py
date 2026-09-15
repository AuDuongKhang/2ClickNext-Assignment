from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render

from .selectors import get_dashboard_follow_ups, get_recent_opportunities


def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    return JsonResponse({"status": "ok", "database": "ok"})


def dashboard(request):
    return render(
        request,
        "core/dashboard.html",
        {
            **get_dashboard_follow_ups(),
            "recent_opportunities": get_recent_opportunities(),
        },
    )
