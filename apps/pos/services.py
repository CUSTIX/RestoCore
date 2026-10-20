from uuid import uuid4

from django.db import transaction

from apps.audit.services import record_audit_event
from apps.core.money import as_money
from apps.orders.models import Order, OrderItem

from .models import Payment


class InvalidPayment(ValueError):
    pass


@transaction.atomic
def create_cashier_order(
    *,
    item_name: str,
    quantity: int,
    unit_price,
    actor,
) -> Order:
    order = Order.objects.create()
    item = OrderItem.objects.create(
        order=order,
        item_name=item_name,
        quantity=quantity,
        unit_price=unit_price,
    )

    record_audit_event(
        action="pos.order_created",
        actor=actor,
        target=order,
        after={
            "first_item_id": item.pk,
            "item_name": item.item_name,
            "quantity": item.quantity,
            "unit_price": str(item.unit_price),
        },
    )
    return order


@transaction.atomic
def take_cash_payment(*, order_id: int, amount_tendered, actor) -> Payment:
    order = Order.objects.select_for_update().prefetch_related("items").get(pk=order_id)

    if order.status == Order.Status.CANCELLED:
        raise InvalidPayment("Cancelled orders cannot be paid.")
    if not order.items.exists():
        raise InvalidPayment("An order must contain at least one item before payment.")
    if Payment.objects.filter(order=order).exists():
        raise InvalidPayment("This order is already paid.")

    amount_due = order.total
    tendered = as_money(amount_tendered)
    if tendered < amount_due:
        raise InvalidPayment("Cash tendered is less than the amount due.")

    change_due = as_money(tendered - amount_due)
    payment = Payment.objects.create(
        order=order,
        method=Payment.Method.CASH,
        amount_due=amount_due,
        amount_tendered=tendered,
        change_due=change_due,
        receipt_number=f"RC-{uuid4().hex[:12].upper()}",
        processed_by=actor,
    )

    record_audit_event(
        action="pos.payment_taken",
        actor=actor,
        target=order,
        after={
            "payment_id": payment.pk,
            "receipt_number": payment.receipt_number,
            "amount_due": str(amount_due),
            "amount_tendered": str(tendered),
            "change_due": str(change_due),
            "method": payment.method,
        },
    )
    return payment
