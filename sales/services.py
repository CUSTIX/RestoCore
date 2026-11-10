"""Sales rules: pricing, checkout (order + stock in one transaction), kitchen flow and voids."""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from inventory import services as inventory_services
from sales.models import MenuItem, Order, OrderLine

CENT = Decimal("0.01")
MAX_QTY_PER_LINE = 99

KITCHEN_FLOW = {
    Order.KitchenStatus.QUEUED: Order.KitchenStatus.PREPARING,
    Order.KitchenStatus.PREPARING: Order.KitchenStatus.READY,
    Order.KitchenStatus.READY: Order.KitchenStatus.SERVED,
}


def tax_rate() -> Decimal:
    return Decimal(settings.SALES_TAX_RATE)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def price_lines(quantities: dict[int, int]) -> tuple[list[dict], Decimal, Decimal, Decimal]:
    """Turn {menu_item_id: qty} into priced lines plus subtotal, tax and total."""
    quantities = {pk: q for pk, q in quantities.items() if q}
    if not quantities:
        raise ValidationError("Add at least one item to the order.")
    if any(q < 0 or q > MAX_QTY_PER_LINE for q in quantities.values()):
        raise ValidationError(f"Quantities must be between 1 and {MAX_QTY_PER_LINE}.")
    items = MenuItem.objects.filter(pk__in=quantities, is_available=True).prefetch_related("recipe")
    items = {i.pk: i for i in items}
    missing = set(quantities) - set(items)
    if missing:
        raise ValidationError("Some items are no longer available. Please refresh the menu.")
    lines = []
    for pk, qty in quantities.items():
        item = items[pk]
        lines.append({"item": item, "quantity": qty, "line_total": money(item.price * qty)})
    subtotal = money(sum((line["line_total"] for line in lines), Decimal("0")))
    tax = money(subtotal * tax_rate())
    return lines, subtotal, tax, subtotal + tax


def ingredients_needed(lines: list[dict]) -> dict[int, Decimal]:
    needed: dict[int, Decimal] = defaultdict(Decimal)
    for line in lines:
        for recipe in line["item"].recipe.all():
            needed[recipe.inventory_item_id] += recipe.quantity * line["quantity"]
    return dict(needed)


@transaction.atomic
def place_order(
    *,
    quantities: dict[int, int],
    cashier,
    order_type: str,
    payment_method: str,
    amount_tendered: Decimal | None = None,
    table_label: str = "",
) -> Order:
    """Create a paid order and deduct its ingredients. All or nothing."""
    lines, subtotal, tax, total = price_lines(quantities)

    if payment_method == Order.PaymentMethod.CASH:
        if amount_tendered is None or amount_tendered < total:
            raise ValidationError(f"Cash received must be at least {total:,.2f}.")
        tendered = money(amount_tendered)
    else:
        tendered = total  # card: exact amount, recorded only (no real payment processing)

    order = Order.objects.create(
        order_type=order_type,
        table_label=table_label.strip(),
        payment_method=payment_method,
        subtotal=subtotal,
        tax_rate=tax_rate(),
        tax=tax,
        total=total,
        amount_tendered=tendered,
        change_due=tendered - total,
        cashier=cashier,
    )
    OrderLine.objects.bulk_create(
        [
            OrderLine(
                order=order,
                menu_item=line["item"],
                name=line["item"].name,
                unit_price=line["item"].price,
                quantity=line["quantity"],
                line_total=line["line_total"],
            )
            for line in lines
        ]
    )
    # Raises InsufficientStock (a ValidationError) and rolls back the whole order if short.
    inventory_services.deduct_for_sale(
        ingredients_needed(lines), reference=order.stock_reference, user=cashier
    )
    return order


@transaction.atomic
def advance_kitchen_status(order: Order) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != Order.Status.PAID or order.kitchen_status not in KITCHEN_FLOW:
        raise ValidationError("This order is not active in the kitchen.")
    order.kitchen_status = KITCHEN_FLOW[order.kitchen_status]
    order.save(update_fields=["kitchen_status", "updated_at"])
    return order


@transaction.atomic
def void_order(order: Order, *, user, reason: str) -> Order:
    """Void a paid order and return its ingredients to stock (unless already served)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.VOIDED:
        raise ValidationError("This order is already voided.")
    if not reason.strip():
        raise ValidationError("A reason is required to void an order.")
    if order.kitchen_status != Order.KitchenStatus.SERVED:
        # Food not yet served: ingredients go back to stock. Served food is a real loss.
        inventory_services.reverse_sale(reference=order.stock_reference, user=user)
        order.kitchen_status = Order.KitchenStatus.CANCELLED
    order.status = Order.Status.VOIDED
    order.voided_by = user
    order.voided_at = timezone.now()
    order.void_reason = reason.strip()
    order.save()
    return order


# ---- Menu management ----------------------------------------------------------------------


def save_menu_item(form, recipe_formset) -> MenuItem:
    with transaction.atomic():
        item = form.save()
        recipe_formset.instance = item
        recipe_formset.save()
    return item
