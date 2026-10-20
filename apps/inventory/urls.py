from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "inventory"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="inventory.access_inventory",
            module_name="Inventory",
            module_description="Ingredients, utensils, and decorations will live here.",
        ),
        name="home",
    ),
]
