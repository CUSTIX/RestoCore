"""Root URL configuration for RestoCore."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("manage/system/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.website.urls")),
    path("", include("apps.core.urls")),
    path("bookings/", include("apps.bookings.urls")),
    path("orders/", include("apps.orders.urls")),
    path("inventory/", include("apps.inventory.urls")),
    path("staff/", include("apps.staff.urls")),
    path("payroll/", include("apps.payroll.urls")),
    path("pos/", include("apps.pos.urls")),
    path("reports/", include("apps.reports.urls")),
]
