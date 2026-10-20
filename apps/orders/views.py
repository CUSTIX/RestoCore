from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views import View
from django.views.generic import DetailView, ListView

from apps.core.mixins import ProtectedPermissionMixin

from .forms import OrderItemForm
from .models import Order
from .services import InvalidOrderTransition, add_order_item, transition_order


class OrderListView(ProtectedPermissionMixin, ListView):
    permission_required = "orders.access_orders"
    template_name = "orders/internal_list.html"
    context_object_name = "orders"
    paginate_by = 25

    def get_queryset(self):
        queryset = Order.objects.prefetch_related("items").all()
        status = self.request.GET.get("status")
        valid_statuses = {value for value, _ in Order.Status.choices}
        if status in valid_statuses:
            queryset = queryset.filter(status=status)
        return queryset


class OrderDetailView(ProtectedPermissionMixin, DetailView):
    permission_required = "orders.access_orders"
    template_name = "orders/detail.html"
    context_object_name = "order"
    queryset = Order.objects.prefetch_related("items")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["item_form"] = OrderItemForm()
        context["order_total"] = self.object.total
        return context


class OrderAddItemView(ProtectedPermissionMixin, View):
    permission_required = "orders.manage_orders"

    def post(self, request, pk):
        form = OrderItemForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Check the item details and try again.")
            return redirect("orders:detail", pk=pk)

        try:
            add_order_item(
                order_id=pk,
                item_name=form.cleaned_data["item_name"],
                quantity=form.cleaned_data["quantity"],
                unit_price=form.cleaned_data["unit_price"],
                actor=request.user,
            )
        except Order.DoesNotExist as exc:
            raise Http404 from exc
        except InvalidOrderTransition:
            messages.error(request, "Items can only be added to ongoing orders.")
        else:
            messages.success(request, "Order item added.")

        return redirect("orders:detail", pk=pk)


class OrderStatusUpdateView(ProtectedPermissionMixin, View):
    permission_required = "orders.manage_orders"

    def post(self, request, pk):
        new_status = request.POST.get("status", "")
        try:
            transition_order(order_id=pk, new_status=new_status, actor=request.user)
        except Order.DoesNotExist as exc:
            raise Http404 from exc
        except InvalidOrderTransition:
            messages.error(request, "That order status change is not allowed.")
        else:
            messages.success(request, "Order status updated.")

        return redirect("orders:detail", pk=pk)
