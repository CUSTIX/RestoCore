import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.http import urlencode
from django.utils.safestring import mark_safe
from django.views.generic import TemplateView, View

from core import throttle
from core.mixins import RoleRequiredMixin
from core.pagination import paginate
from core.roles import CASHIER, KITCHEN, MANAGEMENT
from sales import selectors, services
from sales.forms import (
    MenuCategoryForm,
    MenuItemForm,
    OrderFilterForm,
    PosForm,
    RecipeFormSet,
    SelfOrderForm,
    SelfOrderSearchForm,
    TableQrForm,
    VoidForm,
    clean_table_label,
)
from sales.models import MenuItem, Order, SelfOrder

POS_ROLES = (*MANAGEMENT, CASHIER)
KITCHEN_ROLES = (*MANAGEMENT, KITCHEN)


def _uuid_or_none(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError):
        return None


class PosView(RoleRequiredMixin, TemplateView):
    allowed_roles = POS_ROLES
    template_name = "sales/pos.html"

    def get(self, request, *args, **kwargs):
        # ?self_order=<token>: a customer's QR order, opened from Customer orders to be charged.
        self.self_order = None
        token = request.GET.get("self_order")
        if token:
            self.self_order = selectors.self_order_by_token(_uuid_or_none(token))
            if self.self_order is None:
                messages.error(request, "That customer order wasn't found.")
                return redirect("sales:self_order_list")
            if self.self_order.order_id:
                messages.info(request, f"Order {self.self_order.code} is already paid.")
                return redirect("sales:order_detail", pk=self.self_order.order_id)
            if self.self_order.status != SelfOrder.Status.PENDING:
                status = self.self_order.get_status_display().lower()
                messages.error(request, f"Order {self.self_order.code} is {status}.")
                return redirect("sales:self_order_list")
        return super().get(request, *args, **kwargs)

    def get_context_data(self, form=None, **kwargs):
        menu = selectors.pos_menu()
        self_order = getattr(self, "self_order", None)
        missing = []
        if form is None:
            # A fresh token per new order screen; a re-rendered form (after an error) keeps its
            # own. A customer's order brings its own token and its items, type and table.
            initial = {"checkout_token": uuid.uuid4()}
            if self_order is not None:
                shown = {m["item"].pk for m in menu}
                initial = {
                    "checkout_token": self_order.token,
                    "self_order": self_order.token,
                    "order_type": self_order.order_type,
                    "table_label": self_order.table_label,
                    **{
                        f"qty_{line.menu_item_id}": line.quantity for line in self_order.lines.all()
                    },
                }
                missing = [
                    line for line in self_order.lines.all() if line.menu_item_id not in shown
                ]
            form = PosForm(menu_items=[m["item"] for m in menu], initial=initial)
        elif self_order is None and form.is_bound:
            self_order = selectors.self_order_by_token(_uuid_or_none(form.data.get("self_order")))
        rows = [{**m, "field": form[f"qty_{m['item'].pk}"]} for m in menu]
        return {
            **super().get_context_data(**kwargs),
            "form": form,
            "rows": rows,
            "self_order": self_order,
            "self_order_missing": missing,
            # Recipes + stock let the POS check the whole order, not just one dish at a time.
            "pos_data": {
                "recipes": {str(m["item"].pk): m["recipe"] for m in menu if m["recipe"]},
                "stock": selectors.pos_ingredient_stock(menu),
            },
            "tax_rate": services.tax_rate(),
            "active_section": "pos",
        }

    def post(self, request, *args, **kwargs):
        menu_items = [m["item"] for m in selectors.pos_menu()]
        form = PosForm(request.POST, menu_items=menu_items)
        token = form.data.get("checkout_token")
        already = services.order_for_checkout_token(token)
        if already is not None:  # double-click / refresh: never charge twice
            messages.info(request, f"Order {already.number} was already charged.")
            return redirect("sales:order_detail", pk=already.pk)
        if form.is_valid():
            checkout = {
                "quantities": form.quantities(),
                "cashier": request.user,
                "order_type": form.cleaned_data["order_type"],
                "table_label": form.cleaned_data["table_label"],
                "payment_method": form.cleaned_data["payment_method"],
                "amount_tendered": form.cleaned_data["amount_tendered"],
            }
            try:
                if form.cleaned_data["self_order"]:
                    self_order = selectors.self_order_by_token(form.cleaned_data["self_order"])
                    if self_order is None:
                        raise ValidationError("That customer order wasn't found.")
                    order = services.charge_self_order(self_order, **checkout)
                else:
                    order = services.place_order(
                        checkout_token=form.cleaned_data["checkout_token"], **checkout
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
            "void_returns_stock": services.voiding_returns_stock(order),
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
        orders = list(selectors.kitchen_queue())
        statuses = (
            Order.KitchenStatus.QUEUED,
            Order.KitchenStatus.PREPARING,
            Order.KitchenStatus.READY,
        )
        columns = [
            (s.value, s.label, sum(1 for o in orders if o.kitchen_status == s)) for s in statuses
        ]
        return {
            **super().get_context_data(**kwargs),
            "orders": orders,
            "columns": columns,
            "active_section": "kitchen",
        }


class KitchenAdvanceView(RoleRequiredMixin, View):
    allowed_roles = KITCHEN_ROLES

    def post(self, request, pk):
        order = get_object_or_404(Order, pk=pk)
        try:
            order = services.advance_kitchen_status(order, expected=request.POST.get("from"))
        except services.KitchenTicketMoved as moved:
            messages.info(request, f"{moved} Nothing changed.")
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
            "category_form": MenuCategoryForm(),
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


class MenuCategoryCreateView(RoleRequiredMixin, View):
    allowed_roles = MANAGEMENT

    def post(self, request):
        form = MenuCategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category {form.cleaned_data['name']} added.")
        else:
            messages.error(request, " ".join(e for errs in form.errors.values() for e in errs))
        return redirect("sales:menu_list")


# ---- Customer self-ordering: staff side ---------------------------------------------------


class SelfOrderListView(RoleRequiredMixin, TemplateView):
    """The cashier's side: type the code the customer reads out, or pick from the waiting list."""

    allowed_roles = POS_ROLES
    template_name = "sales/self_order_list.html"

    def get(self, request, *args, **kwargs):
        form = SelfOrderSearchForm(request.GET or None)
        if form.is_valid():
            code = services.normalize_code(form.cleaned_data["code"])
            found = selectors.open_self_order_by_code(code)
            if found is not None:
                return redirect(f"{reverse('sales:pos')}?self_order={found.token}")
            messages.error(
                request,
                f"No open order with code {code or '?'}. Check the code on the customer's "
                "screen: unpaid orders expire after an hour.",
            )
        return self.render_to_response(self.get_context_data(search_form=form))

    def get_context_data(self, search_form=None, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "search_form": search_form or SelfOrderSearchForm(),
            "page_obj": paginate(self.request, selectors.open_self_orders()),
            "active_section": "self_orders",
        }


class SelfOrderCancelView(RoleRequiredMixin, View):
    allowed_roles = POS_ROLES

    def post(self, request, pk):
        self_order = get_object_or_404(SelfOrder, pk=pk)
        try:
            services.cancel_self_order(self_order)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, f"Customer order {self_order.code} cancelled.")
        return redirect("sales:self_order_list")


class TableQrView(RoleRequiredMixin, TemplateView):
    """Printable QR codes: one per table, plus one for the counter (take away)."""

    allowed_roles = MANAGEMENT
    template_name = "sales/table_qr.html"

    def get_context_data(self, **kwargs):
        form = TableQrForm(self.request.GET or None)
        if not form.is_bound:
            tables = [str(n) for n in range(1, 9)]  # the form's initial "1-8"
        else:
            tables = form.cleaned_data["tables"] if form.is_valid() else []
        start = self.request.build_absolute_uri(reverse("ordering:start"))
        cards = [{"label": "Counter", "hint": "Order ahead, pay at the counter", "url": start}]
        cards += [
            {
                "label": f"Table {t}",
                "hint": "Scan to order",
                "url": f"{start}?{urlencode({'table': t})}",
            }
            for t in tables
        ]
        for card in cards:
            # Safe: the SVG is generated by qrcode from a URL we built, not from user HTML.
            card["svg"] = mark_safe(services.qr_svg(card["url"]))  # noqa: S308
        return {
            **super().get_context_data(**kwargs),
            "form": form,
            "cards": cards,
            "active_section": "table_qr",
        }


# ---- Customer self-ordering: public side (no login) ---------------------------------------

SESSION_KEY = "self_orders"


class SelfOrderStartView(TemplateView):
    """The page a table QR code opens: the menu with quantities, then "Done ordering"."""

    template_name = "sales/self_order_start.html"

    def get_context_data(self, form=None, **kwargs):
        menu = selectors.pos_menu()
        table = clean_table_label(self.request.GET.get("table", ""))
        if form is None:
            form = SelfOrderForm(
                menu_items=[m["item"] for m in menu],
                initial={
                    "order_type": Order.OrderType.DINE_IN if table else Order.OrderType.TAKEAWAY,
                    "table_label": table,
                },
            )
        rows = [{**m, "field": form[f"qty_{m['item'].pk}"]} for m in menu]
        recent = selectors.self_orders_by_tokens(self.request.session.get(SESSION_KEY, []))
        return {
            **super().get_context_data(**kwargs),
            "form": form,
            "rows": rows,
            "table": table or form["table_label"].value() or "",
            "tax_rate": services.tax_rate(),
            "open_orders": [o for o in recent if o.status in ("pending", "paid")][:3],
        }

    def post(self, request, *args, **kwargs):
        menu_items = [m["item"] for m in selectors.pos_menu()]
        form = SelfOrderForm(request.POST, menu_items=menu_items)
        if form.is_valid():
            try:
                self_order = services.create_self_order(
                    quantities=form.quantities(),
                    order_type=form.cleaned_data["order_type"],
                    table_label=form.cleaned_data["table_label"],
                    ip=throttle.client_ip(request),
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                mine = [str(self_order.token), *request.session.get(SESSION_KEY, [])][:10]
                request.session[SESSION_KEY] = mine
                return redirect("ordering:status", token=self_order.token)
        return self.render_to_response(self.get_context_data(form=form))


class SelfOrderStatusView(TemplateView):
    """The customer's screen: the code to tell the cashier, then payment and kitchen progress.
    Reached by an unguessable link (the token), so it works even if the phone drops cookies."""

    template_name = "sales/self_order_status.html"

    def get_context_data(self, **kwargs):
        self_order = selectors.self_order_by_token(kwargs["token"])
        if self_order is None:
            raise Http404
        order = self_order.order
        done = (Order.KitchenStatus.SERVED, Order.KitchenStatus.CANCELLED)
        live = self_order.status == SelfOrder.Status.PENDING or (
            order is not None
            and order.status == Order.Status.PAID
            and order.kitchen_status not in done
        )
        return {
            **super().get_context_data(**kwargs),
            "self_order": self_order,
            "order": order,
            "live": live,
            "steps": _progress(self_order),
        }


def _progress(self_order) -> list[dict]:
    """Ordered -> Paid -> Preparing -> Ready, for the customer's progress tracker."""
    reached = 0
    order = self_order.order
    if self_order.status == SelfOrder.Status.PAID and order is not None:
        reached = {"queued": 1, "preparing": 2, "ready": 3, "served": 3}.get(
            order.kitchen_status, 1
        )
    labels = ["Ordered", "Paid", "Preparing", "Ready"]
    return [
        {"label": label, "done": i <= reached, "current": i == reached}
        for i, label in enumerate(labels)
    ]


class SelfOrderCancelPublicView(View):
    """The customer cancels their own unpaid order (from their status link)."""

    def post(self, request, token):
        self_order = selectors.self_order_by_token(token)
        if self_order is None:
            raise Http404
        try:
            services.cancel_self_order(self_order)
        except ValidationError as exc:
            messages.error(request, exc.messages[0])
        else:
            messages.success(request, "Your order was cancelled.")
        return redirect("ordering:status", token=token)
