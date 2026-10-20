from django.urls import path

from .views import InventoryItemCreateView, InventoryListView, StockMovementCreateView

app_name = "inventory"

urlpatterns = [
    path("", InventoryListView.as_view(), name="home"),
    path("new/", InventoryItemCreateView.as_view(), name="create"),
    path("<int:pk>/movement/", StockMovementCreateView.as_view(), name="movement"),
]
