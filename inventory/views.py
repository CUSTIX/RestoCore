from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import FormView, TemplateView

from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import KITCHEN, MANAGEMENT
from inventory import selectors, services
from inventory.forms import ItemFilterForm, ItemForm, MovementForm, NewItemForm
from inventory.models import InventoryItem

VIEW_ROLES = (*MANAGEMENT, KITCHEN)


class ItemListView(RoleRequiredMixin, TemplateView):
    allowed_roles = VIEW_ROLES
    template_name = "inventory/list.html"

    def get_context_data(self, **kwargs):
        form = ItemFilterForm(self.request.GET or None)
        f = form.cleaned_data if form.is_valid() else {}
        qs = selectors.filter_items(q=f.get("q", ""), low_only=f.get("low", False))
        return {
            **super().get_context_data(**kwargs),
            "filter_form": form,
            "page_obj": paginate(self.request, qs, per_page=25),
            "low_count": selectors.low_stock_items().count(),
            "active_section": "inventory",
        }


class ItemDetailView(RoleRequiredMixin, FormView):
    """Item details, its movement ledger, and the form to receive / waste / count stock."""

    allowed_roles = VIEW_ROLES
    template_name = "inventory/detail.html"
    form_class = MovementForm

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(InventoryItem, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "item": self.item,
            "page_obj": paginate(self.request, selectors.movements_for(self.item)),
            "active_section": "inventory",
        }

    def form_valid(self, form):
        action, qty = form.cleaned_data["action"], form.cleaned_data["quantity"]
        note, user = form.cleaned_data["note"], self.request.user
        try:
            if action == "receive":
                services.receive_stock(item_id=self.item.pk, quantity=qty, note=note, user=user)
            elif action == "waste":
                services.record_waste(item_id=self.item.pk, quantity=qty, note=note, user=user)
            elif (
                services.record_count(item_id=self.item.pk, counted=qty, note=note, user=user)
                is None
            ):
                messages.info(self.request, "Count matches the system. Nothing changed.")
                return redirect("inventory:detail", pk=self.item.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Stock updated.")
        return redirect("inventory:detail", pk=self.item.pk)


class ItemCreateView(RoleRequiredMixin, FormView):
    allowed_roles = MANAGEMENT
    template_name = "inventory/form.html"
    form_class = NewItemForm
    extra_context = {"title": "New inventory item", "active_section": "inventory"}

    def form_valid(self, form):
        item = services.create_item(user=self.request.user, **form.cleaned_data)
        messages.success(self.request, f"{item.name} added.")
        return redirect("inventory:detail", pk=item.pk)


class ItemUpdateView(RoleRequiredMixin, FormView):
    allowed_roles = MANAGEMENT
    template_name = "inventory/form.html"
    form_class = ItemForm
    extra_context = {"title": "Edit inventory item", "active_section": "inventory"}

    def dispatch(self, request, *args, **kwargs):
        self.item = get_object_or_404(InventoryItem, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        return {**super().get_form_kwargs(), "instance": self.item}

    def form_valid(self, form):
        services.update_item(self.item, **form.cleaned_data)
        messages.success(self.request, "Item updated.")
        return redirect("inventory:detail", pk=self.item.pk)
