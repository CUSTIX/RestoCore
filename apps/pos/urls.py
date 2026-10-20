from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "pos"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="pos.access_pos",
            module_name="Point of Sale",
            module_description="Cashier and receipt workflows will follow the trunk.",
        ),
        name="home",
    ),
]
