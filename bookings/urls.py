from django.urls import path

from bookings import views

app_name = "bookings"

urlpatterns = [
    path("", views.BookingListView.as_view(), name="list"),
    path("new/", views.BookingCreateView.as_view(), name="create"),
    path("<int:pk>/", views.BookingDetailView.as_view(), name="detail"),
    path("<int:pk>/edit/", views.BookingUpdateView.as_view(), name="update"),
    path("<int:pk>/status/", views.BookingStatusView.as_view(), name="status"),
]
