from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.inventory.models import InventoryItem, StockMovement


@pytest.mark.django_db
def test_inventory_item_supports_restaurant_item_kinds():
    ingredient = InventoryItem.objects.create(
        name="Rice",
        sku="ING-RICE",
        kind=InventoryItem.Kind.INGREDIENT,
        unit="kg",
    )

    assert ingredient.kind == InventoryItem.Kind.INGREDIENT


@pytest.mark.django_db
def test_stock_movement_preserves_fractional_quantity():
    item = InventoryItem.objects.create(
        name="Cooking oil",
        sku="ING-OIL",
        kind=InventoryItem.Kind.INGREDIENT,
        unit="liter",
    )
    movement = StockMovement.objects.create(
        item=item,
        movement_type=StockMovement.Type.USAGE,
        quantity_delta=Decimal("-0.375"),
    )
    movement.refresh_from_db()

    assert movement.quantity_delta == Decimal("-0.375")


@pytest.mark.django_db
def test_stock_movement_rejects_zero_quantity():
    item = InventoryItem.objects.create(
        name="Plate",
        sku="UT-PLATE",
        kind=InventoryItem.Kind.UTENSIL,
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        StockMovement.objects.create(
            item=item,
            movement_type=StockMovement.Type.ADJUSTMENT,
            quantity_delta=Decimal("0"),
        )
