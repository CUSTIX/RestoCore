from django.urls import path

from sales import views

app_name = "sales"

urlpatterns = [
    path("pos/", views.PosView.as_view(), name="pos"),
    path("orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/void/", views.OrderVoidView.as_view(), name="order_void"),
    path("self-orders/", views.SelfOrderListView.as_view(), name="self_order_list"),
    path(
        "self-orders/<int:pk>/cancel/",
        views.SelfOrderCancelView.as_view(),
        name="self_order_cancel",
    ),
    path("table-qr/", views.TableQrView.as_view(), name="table_qr"),
    path("kitchen/", views.KitchenView.as_view(), name="kitchen"),
    path("kitchen/<int:pk>/advance/", views.KitchenAdvanceView.as_view(), name="kitchen_advance"),
    path("menu/", views.MenuListView.as_view(), name="menu_list"),
    path("menu/new/", views.MenuItemEditView.as_view(), name="menu_create"),
    path("menu/categories/new/", views.MenuCategoryCreateView.as_view(), name="category_create"),
    path("menu/<int:pk>/edit/", views.MenuItemEditView.as_view(), name="menu_update"),
]
