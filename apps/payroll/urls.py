from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "payroll"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="payroll.access_payroll",
            module_name="Payroll",
            module_description="Payroll runs and payslips will follow the policy foundation.",
        ),
        name="home",
    ),
]
