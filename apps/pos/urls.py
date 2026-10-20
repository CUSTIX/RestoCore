from django.urls import path

from .views import CashierView, CheckoutRedirectView, CheckoutView, ReceiptView

app_name = "pos"

urlpatterns = [
    path("", CashierView.as_view(), name="home"),
    path("orders/<int:pk>/pay/", CheckoutRedirectView.as_view(), name="pay"),
    path("orders/<int:pk>/checkout/", CheckoutView.as_view(), name="checkout"),
    path("receipts/<int:pk>/", ReceiptView.as_view(), name="receipt"),
]
