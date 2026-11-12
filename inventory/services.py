"""Stock changes. Every change goes through record_movement so the ledger always matches."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from inventory.models import InventoryItem, StockMovement


class InsufficientStock(ValidationError):
    """Raised when a sale needs more stock than is on hand. Lists every short item."""

    def __init__(self, shortages: list[tuple[str, Decimal, Decimal, str]]):
        self.shortages = shortages
        lines = [
            f"{name}: need {need.normalize():f} {unit}, have {have.normalize():f} {unit}"
            for name, need, have, unit in shortages
        ]
        super().__init__("Not enough stock. " + "; ".join(lines))


@transaction.atomic
def create_item(*, user=None, **data) -> InventoryItem:
    opening = data.pop("quantity", None) or Decimal("0")
    item = InventoryItem.objects.create(**data)
    if opening > 0:
        _apply(item, opening, StockMovement.Reason.PURCHASE, note="Opening stock", user=user)
    return item


UNIT_LOCKED = (
    "The unit can't change once stock has been recorded: every quantity in the history and in "
    "recipes would silently change meaning (0.2 kg would become 0.2 g). Create a new item instead."
)


def unit_is_locked(item: InventoryItem) -> bool:
    return bool(item.pk) and item.movements.exists()


def update_item(item: InventoryItem, **data) -> InventoryItem:
    data.pop("quantity", None)  # quantity only changes through movements
    # Compare with the stored unit: a ModelForm has already copied the new value onto `item`.
    stored_unit = InventoryItem.objects.values_list("unit", flat=True).get(pk=item.pk)
    if "unit" in data and data["unit"] != stored_unit and unit_is_locked(item):
        raise ValidationError(UNIT_LOCKED)
    for field, value in data.items():
        setattr(item, field, value)
    item.save()
    return item


def _apply(item: InventoryItem, change: Decimal, reason: str, *, reference="", note="", user=None):
    new_quantity = item.quantity + change
    if new_quantity < 0:
        raise ValidationError(
            f"{item.name} cannot go below zero (on hand {item.quantity.normalize():f})."
        )
    item.quantity = new_quantity
    item.save(update_fields=["quantity", "updated_at"])
    return StockMovement.objects.create(
        item=item,
        change=change,
        quantity_after=new_quantity,
        reason=reason,
        reference=reference,
        note=note,
        created_by=user,
    )


@transaction.atomic
def record_movement(
    *, item_id: int, change: Decimal, reason: str, note="", reference="", user=None
) -> StockMovement:
    if change == 0:
        raise ValidationError("The quantity change cannot be zero.")
    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    return _apply(item, change, reason, reference=reference, note=note, user=user)


def receive_stock(*, item_id: int, quantity: Decimal, note="", user=None) -> StockMovement:
    if quantity <= 0:
        raise ValidationError("Received quantity must be more than zero.")
    return record_movement(
        item_id=item_id, change=quantity, reason=StockMovement.Reason.PURCHASE, note=note, user=user
    )


def record_waste(*, item_id: int, quantity: Decimal, note="", user=None) -> StockMovement:
    if quantity <= 0:
        raise ValidationError("Waste quantity must be more than zero.")
    return record_movement(
        item_id=item_id, change=-quantity, reason=StockMovement.Reason.WASTE, note=note, user=user
    )


@transaction.atomic
def record_count(*, item_id: int, counted: Decimal, note="", user=None) -> StockMovement | None:
    """Set the on-hand quantity to a physical count. Returns None if nothing changed."""
    if counted < 0:
        raise ValidationError("A stock count cannot be negative.")
    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    change = counted - item.quantity
    if change == 0:
        return None
    return _apply(item, change, StockMovement.Reason.COUNT, note=note, user=user)


@transaction.atomic
def deduct_for_sale(requirements: dict[int, Decimal], *, reference: str, user=None) -> None:
    """Deduct all ingredients for a sale, or nothing at all if any item is short.

    Must run inside the caller's transaction so the order and the stock change commit together.
    Items are locked in id order so concurrent sales cannot deadlock or oversell.
    """
    items = {
        i.pk: i
        for i in InventoryItem.objects.select_for_update()
        .filter(pk__in=requirements)
        .order_by("pk")
    }
    shortages = [
        (items[pk].name, need, items[pk].quantity, items[pk].unit)
        for pk, need in sorted(requirements.items())
        if pk in items and items[pk].quantity < need
    ]
    if shortages:
        raise InsufficientStock(shortages)
    for pk, need in sorted(requirements.items()):
        if need > 0 and pk in items:
            _apply(items[pk], -need, StockMovement.Reason.SALE, reference=reference, user=user)


@transaction.atomic
def reverse_sale(*, reference: str, user=None) -> None:
    """Put back exactly what a sale deducted (from the ledger, not the current recipe).

    Idempotent: anything already returned for this reference is not returned twice.
    """
    net: dict[int, Decimal] = {}
    for m in StockMovement.objects.filter(
        reference=reference,
        reason__in=(StockMovement.Reason.SALE, StockMovement.Reason.SALE_VOID),
    ):
        net[m.item_id] = net.get(m.item_id, Decimal("0")) + m.change
    to_return = {pk: -change for pk, change in net.items() if change < 0}
    items = InventoryItem.objects.select_for_update().filter(pk__in=to_return).order_by("pk")
    for item in items:
        _apply(
            item, to_return[item.pk], StockMovement.Reason.SALE_VOID, reference=reference, user=user
        )
