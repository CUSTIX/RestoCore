from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import DetailView, FormView

from apps.core.mixins import ProtectedPermissionMixin
from apps.orders.models import Order

from .forms import CashierOrderForm, CashPaymentForm
from .models import Payment
from .services import InvalidPayment, create_cashier_order, take_cash_payment


class CashierView(ProtectedPermissionMixin, FormView):
    permission_required = "pos.access_pos"
    template_name = "pos/cashier.html"
    form_class = CashierOrderForm

    def form_valid(self, form):
        order = create_cashier_order(
            item_name=form.cleaned_data["item_name"],
            quantity=form.cleaned_data["quantity"],
            unit_price=form.cleaned_data["unit_price"],
            actor=self.request.user,
        )
        messages.success(self.request, f"Order #{order.pk} created.")
        return redirect("orders:detail", pk=order.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["open_orders"] = (
            Order.objects.exclude(status__in=[Order.Status.SERVED, Order.Status.CANCELLED])
            .prefetch_related("items")
            .order_by("-created_at")[:12]
        )
        return context


class CheckoutView(ProtectedPermissionMixin, FormView):
    permission_required = "pos.take_payment"
    template_name = "pos/checkout.html"
    form_class = CashPaymentForm

    def dispatch(self, request, *args, **kwargs):
        self.order = Order.objects.prefetch_related("items").filter(pk=kwargs["pk"]).first()
        if self.order is None:
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            payment = take_cash_payment(
                order_id=self.order.pk,
                amount_tendered=form.cleaned_data["amount_tendered"],
                actor=self.request.user,
            )
        except InvalidPayment as exc:
            form.add_error("amount_tendered", str(exc))
            return self.form_invalid(form)

        messages.success(self.request, "Payment recorded.")
        return redirect("pos:receipt", pk=payment.pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["order"] = self.order
        context["order_total"] = self.order.total
        return context


class ReceiptView(ProtectedPermissionMixin, DetailView):
    permission_required = "pos.access_pos"
    template_name = "pos/receipt.html"
    context_object_name = "payment"
    queryset = Payment.objects.select_related("order", "processed_by").prefetch_related(
        "order__items"
    )


class CheckoutRedirectView(ProtectedPermissionMixin, View):
    permission_required = "pos.take_payment"

    def get(self, request, pk):
        payment = Payment.objects.filter(order_id=pk).first()
        if payment is not None:
            return redirect("pos:receipt", pk=payment.pk)
        return redirect("pos:checkout", pk=pk)
