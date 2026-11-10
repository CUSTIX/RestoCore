from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from inventory import services
from inventory.models import InventoryItem, StockMovement

D = Decimal


@pytest.fixture
def flour(db):
    return services.create_item(
        name="Flour", unit="kg", quantity=D("10"), reorder_level=D("3"), cost_per_unit=D("60")
    )


def test_opening_stock_is_recorded_in_ledger(flour):
    movement = flour.movements.get()
    assert movement.change == D("10") and movement.quantity_after == D("10")


def test_receive_and_waste(flour):
    services.receive_stock(item_id=flour.pk, quantity=D("5"))
    services.record_waste(item_id=flour.pk, quantity=D("2.5"), note="spilled")
    flour.refresh_from_db()
    assert flour.quantity == D("12.5")
    assert flour.movements.count() == 3


def test_waste_cannot_go_below_zero(flour):
    with pytest.raises(ValidationError, match="below zero"):
        services.record_waste(item_id=flour.pk, quantity=D("11"))
    flour.refresh_from_db()
    assert flour.quantity == D("10")


def test_non_positive_quantities_rejected(flour):
    with pytest.raises(ValidationError):
        services.receive_stock(item_id=flour.pk, quantity=D("0"))
    with pytest.raises(ValidationError):
        services.record_waste(item_id=flour.pk, quantity=D("-1"))


def test_count_sets_exact_quantity_and_skips_no_change(flour):
    movement = services.record_count(item_id=flour.pk, counted=D("7"))
    assert movement.change == D("-3")
    assert services.record_count(item_id=flour.pk, counted=D("7")) is None


def test_update_item_never_changes_quantity(flour):
    services.update_item(flour, name="Flour (AP)", quantity=D("999"))
    flour.refresh_from_db()
    assert flour.quantity == D("10") and flour.name == "Flour (AP)"


def test_deduct_for_sale_is_all_or_nothing(flour):
    sugar = services.create_item(name="Sugar", unit="kg", quantity=D("1"))
    with pytest.raises(services.InsufficientStock) as exc:
        services.deduct_for_sale({flour.pk: D("2"), sugar.pk: D("5")}, reference="ORDER-1")
    assert "Sugar" in str(exc.value)
    flour.refresh_from_db()
    assert flour.quantity == D("10")  # flour untouched because sugar was short
    assert not StockMovement.objects.filter(reason="sale").exists()


def test_reverse_sale_restores_exactly_once(flour):
    services.deduct_for_sale({flour.pk: D("4")}, reference="ORDER-9")
    services.reverse_sale(reference="ORDER-9")
    services.reverse_sale(reference="ORDER-9")  # second call must not add stock again
    flour.refresh_from_db()
    assert flour.quantity == D("10")


def test_low_stock_flag(flour):
    services.record_count(item_id=flour.pk, counted=D("3"))
    assert InventoryItem.objects.get(pk=flour.pk).is_low
