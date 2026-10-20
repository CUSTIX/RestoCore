from django.urls import path

from .views import OrderAddItemView, OrderDetailView, OrderListView, OrderStatusUpdateView

app_name = "orders"

urlpatterns = [
    path("", OrderListView.as_view(), name="home"),
    path("<int:pk>/", OrderDetailView.as_view(), name="detail"),
    path("<int:pk>/items/", OrderAddItemView.as_view(), name="add_item"),
    path("<int:pk>/status/", OrderStatusUpdateView.as_view(), name="status"),
]
