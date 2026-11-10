from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import TemplateView, View

from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import CASHIER, KITCHEN, MANAGEMENT
from sales import selectors, services
from sales.forms import MenuItemForm, OrderFilterForm, PosForm, RecipeFormSet, VoidForm
from sales.models import MenuItem, Order

POS_ROLES = (*MANAGEMENT, CASHIER)
KITCHEN_ROLES = (*MANAGEMENT, KITCHEN)


class PosView(RoleRequiredMixin, TemplateView):
    allowed_roles = POS_ROLES
    template_name = "sales/pos.html"

    def get_context_data(self, form=None, **kwargs):
        menu = selectors.pos_menu()
        form = form or PosForm(menu_items=[m["item"] for m in menu])
        rows = [{**m, "field": form[f"qty_{m['item'].pk}"]} for m in menu]
        return {
            **super().get_context_data(**kwargs),
            "form": form,
            "rows": rows,
            "tax_rate": services.tax_rate(),
            "active_section": "pos",
        }

    def post(self, request, *args, **kwargs):
        menu_items = [m["item"] for m in selectors.pos_menu()]
        form = PosForm(request.POST, menu_items=menu_items)
        if form.is_valid():
            try:
                order = services.place_order(
                    quantities=form.quantities(),
                    cashier=request.user,
                    order_type=form.cleaned_data["order_type"],
                    table_label=form.cleaned_data["table_label"],
                    payment_method=form.cleaned_data["payment_method"],
                    amount_tendered=form.cleaned_data["amount_tendered"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request, f"Order {order.number} paid. Change due: {order.change_due:,.2f}"
                )
                return redirect("sales:order_detail", pk=order.pk)
        return self.render_to_response(self.get_context_data(form=form))


class OrderListView(RoleRequiredMixin, TemplateView):
    allowed_roles = POS_ROLES
    template_name = "sales/order_list.html"

    def get_context_data(self, **kwargs):
        form = OrderFilterForm(self.request.GET or None)
        f = form.cleaned_data if form.is_valid() else {}
        qs = selectors.filter_orders(date=f.get("date"), status=f.get("status", ""))
        return {
            **super().get_context_data(**kwargs),
            "filter_form": form,
            "page_obj": paginate(self.request, qs),
            "summary": selectors.sales_summary(),
            "active_section": "orders",
        }


class OrderDetailView(RoleRequiredMixin, TemplateView):
    allowed_roles = (*POS_ROLES, KITCHEN)
    template_name = "sales/order_detail.html"

    def get_context_data(self, **kwargs):
        try:
            order = selectors.order_with_lines(kwargs["pk"])
        except Order.DoesNotExist as exc:
            raise Http404 from exc
        return {
            **super().get_context_data(**kwargs),
            "order": order,
            "void_form": VoidForm(),
            "active_section": "orders",
        }


class OrderVoidView(RoleRequiredMixin, View):
    allowed_roles = MANAGEMENT

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        form = VoidForm(request.POST)
        if not form.is_valid():
            messages.error(request, "A reason is required to void an order.")
            return redirect("sales:order_detail", pk=pk)
        try:
            services.void_order(order, user=request.user, reason=form.cleaned_data["reason"])
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, f"Order {order.number} voided.")
        return redirect("sales:order_detail", pk=pk)


class KitchenView(RoleRequiredMixin, TemplateView):
    allowed_roles = KITCHEN_ROLES
    template_name = "sales/kitchen.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "orders": selectors.kitchen_queue(),
            "active_section": "kitchen",
        }


class KitchenAdvanceView(RoleRequiredMixin, View):
    allowed_roles = KITCHEN_ROLES

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            order = services.advance_kitchen_status(order)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            status = order.get_kitchen_status_display()
            messages.success(request, f"Order {order.number}: {status}.")
        return redirect("sales:kitchen")


class MenuListView(RoleRequiredMixin, TemplateView):
    allowed_roles = MANAGEMENT
    template_name = "sales/menu_list.html"

    def get_context_data(self, **kwargs):
        qs = selectors.all_menu_items().prefetch_related("recipe")
        return {
            **super().get_context_data(**kwargs),
            "page_obj": paginate(self.request, qs, per_page=30),
            "active_section": "menu",
        }


class MenuItemEditView(RoleRequiredMixin, TemplateView):
    """Create (pk=None) or edit a menu item together with its recipe."""

    allowed_roles = MANAGEMENT
    template_name = "sales/menu_form.html"

    def get_object(self):
        pk = self.kwargs.get("pk")
        return get_object_or_404(MenuItem, pk=pk) if pk else None

    def get_context_data(self, form=None, formset=None, **kwargs):
        item = self.get_object()
        return {
            **super().get_context_data(**kwargs),
            "form": form or MenuItemForm(instance=item),
            "formset": formset or RecipeFormSet(instance=item or MenuItem()),
            "title": f"Edit {item.name}" if item else "New menu item",
            "active_section": "menu",
        }

    def post(self, request, *args, **kwargs):
        item = self.get_object()
        form = MenuItemForm(request.POST, instance=item)
        formset = RecipeFormSet(request.POST, instance=item or MenuItem())
        if form.is_valid() and formset.is_valid():
            saved = services.save_menu_item(form, formset)
            messages.success(request, f"{saved.name} saved.")
            return redirect("sales:menu_list")
        return self.render_to_response(self.get_context_data(form=form, formset=formset))
