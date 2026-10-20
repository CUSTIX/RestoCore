from django import forms

from apps.orders.models import OrderItem


class CashierOrderForm(forms.ModelForm):
    class Meta:
        model = OrderItem
        fields = ("item_name", "quantity", "unit_price")


class CashPaymentForm(forms.Form):
    amount_tendered = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0,
        label="Cash tendered",
    )
