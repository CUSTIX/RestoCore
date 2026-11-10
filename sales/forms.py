from decimal import Decimal

from django import forms

from inventory import selectors as inventory_selectors
from sales.models import MenuItem, Order, RecipeLine
from sales.services import MAX_QTY_PER_LINE


class PosForm(forms.Form):
    """Checkout form. One quantity field per menu item, named qty_<id>."""

    order_type = forms.ChoiceField(choices=Order.OrderType.choices, initial="dine_in")
    table_label = forms.CharField(max_length=20, required=False, label="Table")
    payment_method = forms.ChoiceField(choices=Order.PaymentMethod.choices, initial="cash")
    amount_tendered = forms.DecimalField(
        required=False,
        min_value=Decimal("0"),
        max_digits=10,
        decimal_places=2,
        label="Cash received",
    )

    def __init__(self, *args, menu_items=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.menu_items = list(menu_items)
        for item in self.menu_items:
            self.fields[f"qty_{item.pk}"] = forms.IntegerField(
                min_value=0,
                max_value=MAX_QTY_PER_LINE,
                required=False,
                initial=0,
                label=item.name,
            )

    def quantities(self) -> dict[int, int]:
        return {item.pk: self.cleaned_data.get(f"qty_{item.pk}") or 0 for item in self.menu_items}

    def clean(self):
        cleaned = super().clean()
        if self.menu_items and not any(self.quantities().values()):
            raise forms.ValidationError("Add at least one item to the order.")
        if cleaned.get("order_type") == Order.OrderType.DINE_IN and not cleaned.get("table_label"):
            self.add_error("table_label", "Enter a table for dine-in orders.")
        if (
            cleaned.get("payment_method") == Order.PaymentMethod.CASH
            and cleaned.get("amount_tendered") is None
        ):
            self.add_error("amount_tendered", "Enter the cash received.")
        return cleaned


class VoidForm(forms.Form):
    reason = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={"placeholder": "Why is this order being voided?"}),
    )


class OrderFilterForm(forms.Form):
    date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    status = forms.ChoiceField(required=False, choices=[("", "All"), *Order.Status.choices])


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ("category", "name", "description", "price", "is_available")


class RecipeLineForm(forms.ModelForm):
    class Meta:
        model = RecipeLine
        fields = ("inventory_item", "quantity")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["inventory_item"].queryset = inventory_selectors.active_items()
        self.fields["inventory_item"].label = "Ingredient"
        self.fields["quantity"].label = "Quantity per portion"


RecipeFormSet = forms.inlineformset_factory(
    MenuItem, RecipeLine, form=RecipeLineForm, extra=3, can_delete=True
)
