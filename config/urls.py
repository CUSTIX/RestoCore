from django.contrib import admin
from django.urls import include, path

from config.views import healthz

urlpatterns = [
    path("", include("website.urls")),
    path("book/", include("bookings.public_urls")),
    path("accounts/", include("accounts.urls")),
    path("app/", include("dashboard.urls")),
    path("app/bookings/", include("bookings.urls")),
    path("app/inventory/", include("inventory.urls")),
    path("app/sales/", include("sales.urls")),
    path("app/staff/", include("staff.urls")),
    path("app/payroll/", include("payroll.urls")),
    path("api/", include("api.urls")),
    path("admin/", admin.site.urls),
    path("healthz/", healthz, name="healthz"),
]
