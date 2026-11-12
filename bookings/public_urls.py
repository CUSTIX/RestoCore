from django.urls import path

from bookings import views

app_name = "public_bookings"

urlpatterns = [
    path("", views.PublicBookingView.as_view(), name="create"),
    path("thanks/<str:reference>/", views.PublicThanksView.as_view(), name="thanks"),
    path("availability/", views.AvailabilityView.as_view(), name="availability"),
]
