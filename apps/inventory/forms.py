from decimal import Decimal

from django import forms

from .models import InventoryItem, StockMovement


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ("name", "sku", "kind", "unit", "is_active")

    def clean_sku(self):
        return self.cleaned_data["sku"].strip().upper()


class StockMovementForm(forms.ModelForm):
    class Meta:
        model = StockMovement
        fields = ("movement_type", "quantity_delta", "note")

    def clean_quantity_delta(self):
        value = self.cleaned_data["quantity_delta"]
        if value == Decimal("0"):
            raise forms.ValidationError("Quantity change cannot be zero.")
        return value
