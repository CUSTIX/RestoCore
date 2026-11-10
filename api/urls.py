from django.urls import path

from api import views

app_name = "api"

urlpatterns = [
    path("bookings/", views.bookings_view, name="bookings"),
    path("inventory/low-stock/", views.low_stock_view, name="low_stock"),
    path("sales/summary/", views.sales_summary_view, name="sales_summary"),
    path("menu/", views.menu_view, name="menu"),
    path("staff/on-shift/", views.on_shift_view, name="on_shift"),
]
