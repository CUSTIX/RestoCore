from django.urls import path

from apps.core.views import ModuleLandingView

app_name = "bookings"

urlpatterns = [
    path(
        "",
        ModuleLandingView.as_view(
            permission_required="bookings.access_bookings",
            module_name="Bookings",
            module_description="Booking operations will be added after the trunk is complete.",
        ),
        name="home",
    ),
]
