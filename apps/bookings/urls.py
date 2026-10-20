from django.urls import path

from .views import BookingListView, BookingStatusUpdateView

app_name = "bookings"

urlpatterns = [
    path("", BookingListView.as_view(), name="home"),
    path("<int:pk>/status/", BookingStatusUpdateView.as_view(), name="status"),
]
