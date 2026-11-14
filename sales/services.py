"""Sales rules: pricing, checkout (order + stock in one transaction), kitchen flow and voids."""

import datetime as dt
import secrets
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

import qrcode
import qrcode.constants
import qrcode.image.svg
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from core import throttle
from inventory import selectors as inventory_selectors
from inventory import services as inventory_services
from sales.models import MenuItem, Order, OrderLine, SelfOrder, SelfOrderLine

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


def order_for_checkout_token(token) -> Order | None:
    """The order already created from this POS screen, if any (bad/missing token: None)."""
    try:
        token = uuid.UUID(str(token))
    except (TypeError, ValueError):
        return None
    return Order.objects.filter(checkout_token=token).first()


@transaction.atomic
def place_order(
    *,
    quantities: dict[int, int],
    cashier,
    order_type: str,
    payment_method: str,
    amount_tendered: Decimal | None = None,
    table_label: str = "",
    checkout_token=None,
) -> Order:
    """Create a paid order and deduct its ingredients. All or nothing.

    Idempotent per `checkout_token`: sending the same token again (double-click, refresh,
    network retry) returns the order already created instead of charging twice.
    """
    if checkout_token is not None:
        existing = Order.objects.filter(checkout_token=checkout_token).first()
        if existing is not None:
            return existing
    lines, subtotal, tax, total = price_lines(quantities)

    if payment_method == Order.PaymentMethod.CASH:
        if amount_tendered is None or amount_tendered < total:
            raise ValidationError(f"Cash received must be at least {total:,.2f}.")
        tendered = money(amount_tendered)
    else:
        tendered = total  # card: exact amount, recorded only (no real payment processing)

    try:
        # Savepoint: if a simultaneous request with the same token committed first, the unique
        # constraint fires here and we hand back that order (no lines, no stock moved twice).
        with transaction.atomic():
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
                checkout_token=checkout_token,
            )
    except IntegrityError:
        if checkout_token is None:
            raise
        return Order.objects.get(checkout_token=checkout_token)
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


class KitchenTicketMoved(Exception):
    """The ticket is no longer at the status the cook saw (double tap, or another screen)."""

    def __init__(self, order: Order):
        self.order = order
        super().__init__(f"Order {order.number} is already {order.get_kitchen_status_display()}.")


@transaction.atomic
def advance_kitchen_status(order: Order, *, expected: str | None = None) -> Order:
    """Move a ticket one step along the kitchen flow.

    `expected` is the status shown on the cook's screen. If the ticket has moved on since
    (a double tap, or another kitchen screen), nothing changes and KitchenTicketMoved is
    raised, instead of silently skipping a step, e.g. queued straight to ready.
    """
    order = Order.objects.select_for_update().get(pk=order.pk)
    if expected and order.kitchen_status != expected:
        raise KitchenTicketMoved(order)
    if order.status != Order.Status.PAID or order.kitchen_status not in KITCHEN_FLOW:
        raise ValidationError("This order is not active in the kitchen.")
    order.kitchen_status = KITCHEN_FLOW[order.kitchen_status]
    order.save(update_fields=["kitchen_status", "updated_at"])
    return order


def voiding_returns_stock(order: Order) -> bool:
    """Once the kitchen starts preparing, the ingredients are used even if the order is voided:
    putting them back would make the stock count wrong."""
    return order.kitchen_status == Order.KitchenStatus.QUEUED


@transaction.atomic
def void_order(order: Order, *, user, reason: str) -> Order:
    """Void a paid order. Ingredients go back to stock only if the kitchen hadn't started it."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == Order.Status.VOIDED:
        raise ValidationError("This order is already voided.")
    if not reason.strip():
        raise ValidationError("A reason is required to void an order.")
    if voiding_returns_stock(order):
        # Still queued: nothing was cooked, so the ingredients are back on the shelf.
        inventory_services.reverse_sale(reference=order.stock_reference, user=user)
    if order.kitchen_status in KITCHEN_FLOW:  # queued / preparing / ready: off the board
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


# ---- Customer self-ordering (table QR codes) ----------------------------------------------

SELF_ORDER_TTL = dt.timedelta(minutes=60)  # unpaid longer than this: expired
SELF_ORDERS_PER_IP_PER_HOUR = 30  # a whole restaurant may share one Wi-Fi IP
CODE_ALPHABET = "ACDEFHJKMNPRTVWXY34679"  # no 0/O, 1/I/L, 2/Z, 5/S, 8/B, U/V look-alikes
CODE_LENGTH = 5
TOO_MANY_SELF_ORDERS = "Too many orders from this network. Please order at the counter."


def normalize_code(raw: str) -> str:
    """What the customer read out, as typed by the cashier: '#k7m-4p ' -> 'K7M4P'."""
    return "".join(ch for ch in str(raw).upper() if ch.isalnum())[:8]


def new_code() -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def expire_stale_self_orders() -> int:
    """Mark unpaid orders older than the TTL as expired (frees their codes)."""
    cutoff = timezone.now() - SELF_ORDER_TTL
    return SelfOrder.objects.filter(status=SelfOrder.Status.PENDING, created_at__lt=cutoff).update(
        status=SelfOrder.Status.EXPIRED, updated_at=timezone.now()
    )


def check_stock(lines: list[dict]) -> None:
    """Refuse an order the kitchen can't make right now (dishes share ingredients, so the whole
    order is checked, not one dish at a time)."""
    needed = ingredients_needed(lines)
    stock = inventory_selectors.quantities(needed)
    short = {pk for pk, qty in needed.items() if pk in stock and stock[pk][1] < qty}
    if short:
        dishes = [
            line["item"].name
            for line in lines
            if any(r.inventory_item_id in short for r in line["item"].recipe.all())
        ]
        raise ValidationError(
            f"Sorry, we can't make that many {', '.join(dishes)} right now. "
            "Please lower the quantity or pick something else."
        )


def create_self_order(
    *, quantities: dict[int, int], order_type: str, table_label: str = "", ip: str | None
) -> SelfOrder:
    """A customer's order from their phone: priced and stock-checked, but not paid."""
    if ip is not None and throttle.is_limited(
        "self-order-ip", ip, limit=SELF_ORDERS_PER_IP_PER_HOUR, window=dt.timedelta(hours=1)
    ):
        raise ValidationError(TOO_MANY_SELF_ORDERS)
    lines, subtotal, tax, total = price_lines(quantities)
    check_stock(lines)
    expire_stale_self_orders()
    table = table_label.strip() if order_type == Order.OrderType.DINE_IN else ""
    for _attempt in range(10):
        try:
            with transaction.atomic():
                self_order = SelfOrder.objects.create(
                    code=new_code(),
                    order_type=order_type,
                    table_label=table,
                    subtotal=subtotal,
                    tax=tax,
                    total=total,
                )
                SelfOrderLine.objects.bulk_create(
                    [
                        SelfOrderLine(
                            self_order=self_order,
                            menu_item=line["item"],
                            name=line["item"].name,
                            unit_price=line["item"].price,
                            quantity=line["quantity"],
                            line_total=line["line_total"],
                        )
                        for line in lines
                    ]
                )
            break
        except IntegrityError:  # that code is taken by another open order: draw again
            continue
    else:
        raise ValidationError("Please try again in a moment.")
    if ip is not None:
        throttle.record("self-order-ip", ip)
    return self_order


@transaction.atomic
def charge_self_order(
    self_order: SelfOrder,
    *,
    quantities: dict[int, int],
    cashier,
    order_type: str,
    payment_method: str,
    amount_tendered: Decimal | None = None,
    table_label: str = "",
) -> Order:
    """The cashier checked the customer's order (and may have changed it): take payment.

    Creates the real order (stock deducted, sent to the kitchen) with the self-order's token as
    checkout token, so a double click hands back the same order instead of charging twice.
    """
    self_order = SelfOrder.objects.select_for_update().get(pk=self_order.pk)
    if self_order.order_id:
        return self_order.order
    if self_order.status == SelfOrder.Status.CANCELLED:
        raise ValidationError("This customer order was cancelled. Start a new order instead.")
    # PENDING, or EXPIRED while the cashier had it open: the customer is at the counter.
    order = place_order(
        quantities=quantities,
        cashier=cashier,
        order_type=order_type,
        payment_method=payment_method,
        amount_tendered=amount_tendered,
        table_label=table_label,
        checkout_token=self_order.token,
    )
    self_order.order = order
    self_order.status = SelfOrder.Status.PAID
    self_order.save(update_fields=["order", "status", "updated_at"])
    return order


@transaction.atomic
def cancel_self_order(self_order: SelfOrder) -> SelfOrder:
    """Customer changed their mind, or never came to pay. Only unpaid orders can be cancelled."""
    self_order = SelfOrder.objects.select_for_update().get(pk=self_order.pk)
    if self_order.status not in (SelfOrder.Status.PENDING, SelfOrder.Status.EXPIRED):
        raise ValidationError("This order is already paid or cancelled.")
    self_order.status = SelfOrder.Status.CANCELLED
    self_order.save(update_fields=["status", "updated_at"])
    return self_order


def qr_svg(data: str) -> str:
    """An inline SVG QR code for `data` (a URL we built ourselves)."""
    image = qrcode.make(
        data,
        image_factory=qrcode.image.svg.SvgPathImage,
        box_size=10,
        border=2,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
    )
    svg = image.to_string(encoding="unicode")
    return svg[svg.index("<svg") :]  # drop the XML declaration: it's embedded in HTML
