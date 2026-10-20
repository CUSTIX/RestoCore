from decimal import Decimal

from django.db import transaction

from apps.audit.services import record_audit_event

from .models import InventoryItem, StockMovement


@transaction.atomic
def record_stock_movement(
    *,
    item_id: int,
    movement_type: str,
    quantity_delta: Decimal,
    note: str,
    actor,
) -> StockMovement:
    if quantity_delta == Decimal("0"):
        raise ValueError("Stock movement quantity cannot be zero.")

    item = InventoryItem.objects.select_for_update().get(pk=item_id)
    movement = StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity_delta=quantity_delta,
        note=note,
    )

    record_audit_event(
        action="inventory.stock_movement_recorded",
        actor=actor,
        target=item,
        after={
            "movement_id": movement.pk,
            "movement_type": movement_type,
            "quantity_delta": str(quantity_delta),
        },
        metadata={"note": note},
    )
    return movement
