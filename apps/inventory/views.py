from decimal import Decimal

from django.contrib import messages
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views.generic import CreateView, FormView, ListView

from apps.audit.services import record_audit_event
from apps.core.mixins import ProtectedPermissionMixin

from .forms import InventoryItemForm, StockMovementForm
from .models import InventoryItem
from .services import record_stock_movement


class InventoryListView(ProtectedPermissionMixin, ListView):
    permission_required = "inventory.access_inventory"
    template_name = "inventory/internal_list.html"
    context_object_name = "items"
    paginate_by = 25

    def get_queryset(self):
        balance_field = DecimalField(max_digits=14, decimal_places=3)
        queryset = InventoryItem.objects.annotate(
            stock_balance=Coalesce(
                Sum("stock_movements__quantity_delta"),
                Value(Decimal("0"), output_field=balance_field),
                output_field=balance_field,
            )
        ).order_by("name", "id")

        kind = self.request.GET.get("kind")
        valid_kinds = {value for value, _ in InventoryItem.Kind.choices}
        if kind in valid_kinds:
            queryset = queryset.filter(kind=kind)
        return queryset


class InventoryItemCreateView(ProtectedPermissionMixin, CreateView):
    permission_required = "inventory.manage_inventory"
    form_class = InventoryItemForm
    template_name = "inventory/item_form.html"
    success_url = reverse_lazy("inventory:home")

    def form_valid(self, form):
        response = super().form_valid(form)
        record_audit_event(
            action="inventory.item_created",
            actor=self.request.user,
            target=self.object,
            after={
                "name": self.object.name,
                "sku": self.object.sku,
                "kind": self.object.kind,
                "unit": self.object.unit,
            },
        )
        messages.success(self.request, "Inventory item created.")
        return response


class StockMovementCreateView(ProtectedPermissionMixin, FormView):
    permission_required = "inventory.adjust_stock"
    form_class = StockMovementForm
    template_name = "inventory/stock_movement_form.html"
    success_url = reverse_lazy("inventory:home")

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(InventoryItem, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        record_stock_movement(
            item_id=self.item.pk,
            movement_type=form.cleaned_data["movement_type"],
            quantity_delta=form.cleaned_data["quantity_delta"],
            note=form.cleaned_data["note"],
            actor=self.request.user,
        )
        messages.success(self.request, "Stock movement recorded.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item"] = self.item
        return context
