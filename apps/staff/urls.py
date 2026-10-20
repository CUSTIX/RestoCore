from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "staff"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="staff.access_staff",
            module_name="Staff",
            module_description="Attendance, schedules, requests, and employees will live here.",
        ),
        name="home",
    ),
]
