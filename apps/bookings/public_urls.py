from django.urls import path

from .public_views import PublicBookingSuccessView, PublicBookingView

app_name = "booking_public"

urlpatterns = [
    path("", PublicBookingView.as_view(), name="create"),
    path("received/", PublicBookingSuccessView.as_view(), name="success"),
]
