from django.urls import path

from payroll import views

app_name = "payroll"

urlpatterns = [
    path("", views.PeriodListView.as_view(), name="period_list"),
    path("rates/", views.DeductionRatesView.as_view(), name="rates"),
    path("periods/<int:pk>/", views.PeriodDetailView.as_view(), name="period_detail"),
    path("periods/<int:pk>/action/", views.PeriodActionView.as_view(), name="period_action"),
    path("payslips/<int:pk>/", views.PayslipDetailView.as_view(), name="payslip_detail"),
]
