from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "orders"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="orders.access_orders",
            module_name="Orders",
            module_description="Order workflow features will follow the shared foundation.",
        ),
        name="home",
    ),
]
