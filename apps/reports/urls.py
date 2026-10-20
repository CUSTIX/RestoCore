from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "reports"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="reports.access_reports",
            module_name="Reports",
            module_description="Reports will follow stable source-module data models.",
        ),
        name="home",
    ),
]
