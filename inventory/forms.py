from decimal import Decimal

from django import forms

from inventory.models import InventoryItem


class ItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = ("name", "unit", "reorder_level", "cost_per_unit", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from inventory.services import unit_is_locked

        if self.instance.pk and unit_is_locked(self.instance):
            # Shown but not editable; a disabled field also ignores any posted value.
            self.fields["unit"].disabled = True
            self.fields["unit"].help_text = "Fixed once stock has been recorded."


class NewItemForm(ItemForm):
    quantity = forms.DecimalField(
        min_value=Decimal("0"),
        max_digits=12,
        decimal_places=3,
        initial=Decimal("0"),
        label="Opening quantity",
    )

    class Meta(ItemForm.Meta):
        fields = ("name", "unit", "quantity", "reorder_level", "cost_per_unit", "is_active")


class MovementForm(forms.Form):
    ACTIONS = [
        ("receive", "Receive stock (add)"),
        ("waste", "Record waste (subtract)"),
        ("count", "Stock count (set exact quantity)"),
    ]
    action = forms.ChoiceField(choices=ACTIONS)
    quantity = forms.DecimalField(min_value=Decimal("0"), max_digits=12, decimal_places=3)
    note = forms.CharField(max_length=200, required=False)


class ItemFilterForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search",
        widget=forms.TextInput(attrs={"type": "search", "placeholder": "Item name"}),
    )
    low = forms.BooleanField(required=False, label="Low stock only")
