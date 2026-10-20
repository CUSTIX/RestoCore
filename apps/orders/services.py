from django.db import transaction

from apps.audit.services import record_audit_event

from .models import Order, OrderItem


class InvalidOrderTransition(ValueError):
    pass


ALLOWED_TRANSITIONS = {
    Order.Status.ONGOING: {
        Order.Status.SERVING,
        Order.Status.CANCELLED,
    },
    Order.Status.SERVING: {
        Order.Status.SERVED,
        Order.Status.CANCELLED,
    },
    Order.Status.SERVED: set(),
    Order.Status.CANCELLED: set(),
}


@transaction.atomic
def transition_order(*, order_id: int, new_status: str, actor) -> Order:
    order = Order.objects.select_for_update().get(pk=order_id)
    old_status = order.status

    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise InvalidOrderTransition(f"Cannot move order from {old_status!r} to {new_status!r}.")

    order.status = new_status
    order.save(update_fields=["status", "updated_at"])

    record_audit_event(
        action="orders.status_changed",
        actor=actor,
        target=order,
        before={"status": old_status},
        after={"status": new_status},
    )
    return order


@transaction.atomic
def add_order_item(
    *,
    order_id: int,
    item_name: str,
    quantity: int,
    unit_price,
    actor,
) -> OrderItem:
    order = Order.objects.select_for_update().get(pk=order_id)
    if order.status != Order.Status.ONGOING:
        raise InvalidOrderTransition("Items can only be added while an order is ongoing.")

    item = OrderItem.objects.create(
        order=order,
        item_name=item_name,
        quantity=quantity,
        unit_price=unit_price,
    )
    record_audit_event(
        action="orders.item_added",
        actor=actor,
        target=order,
        after={
            "order_item_id": item.pk,
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
        },
    )
    return item
