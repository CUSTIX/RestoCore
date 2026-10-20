from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.inventory.models import InventoryItem, StockMovement


@pytest.fixture
def manager_user():
    user = get_user_model().objects.create_user(
        email="inventory-manager@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="manager"))
    return user


@pytest.fixture
def inventory_item():
    return InventoryItem.objects.create(
        name="Rice",
        sku="ING-RICE",
        kind=InventoryItem.Kind.INGREDIENT,
        unit="kg",
    )


@pytest.mark.django_db
def test_inventory_list_uses_movement_ledger_for_balance(
    client,
    manager_user,
    inventory_item,
):
    StockMovement.objects.create(
        item=inventory_item,
        movement_type=StockMovement.Type.RECEIPT,
        quantity_delta=Decimal("5.000"),
    )
    StockMovement.objects.create(
        item=inventory_item,
        movement_type=StockMovement.Type.USAGE,
        quantity_delta=Decimal("-1.250"),
    )
    client.force_login(manager_user)

    response = client.get(reverse("inventory:home"))

    assert response.status_code == 200
    assert b"Rice" in response.content
    assert b"3.75" in response.content


@pytest.mark.django_db
def test_manager_can_create_inventory_item(client, manager_user):
    client.force_login(manager_user)

    response = client.post(
        reverse("inventory:create"),
        {
            "name": "Dinner Plate",
            "sku": "ut-plate-01",
            "kind": InventoryItem.Kind.UTENSIL,
            "unit": "piece",
            "is_active": "on",
        },
    )

    assert response.status_code == 302
    item = InventoryItem.objects.get()
    assert item.sku == "UT-PLATE-01"
    assert AuditEvent.objects.filter(
        actor=manager_user,
        action="inventory.item_created",
        target_id=str(item.pk),
    ).exists()


@pytest.mark.django_db
def test_stock_movement_is_recorded_and_audited(client, manager_user, inventory_item):
    client.force_login(manager_user)

    response = client.post(
        reverse("inventory:movement", args=[inventory_item.pk]),
        {
            "movement_type": StockMovement.Type.RECEIPT,
            "quantity_delta": "12.500",
            "note": "Supplier delivery",
        },
    )

    assert response.status_code == 302
    movement = StockMovement.objects.get()
    assert movement.quantity_delta == Decimal("12.500")
    assert AuditEvent.objects.filter(
        actor=manager_user,
        action="inventory.stock_movement_recorded",
        target_id=str(inventory_item.pk),
    ).exists()


@pytest.mark.django_db
def test_stock_movement_form_rejects_zero(client, manager_user, inventory_item):
    client.force_login(manager_user)

    response = client.post(
        reverse("inventory:movement", args=[inventory_item.pk]),
        {
            "movement_type": StockMovement.Type.ADJUSTMENT,
            "quantity_delta": "0",
            "note": "",
        },
    )

    assert response.status_code == 200
    assert StockMovement.objects.count() == 0
    assert b"Quantity change cannot be zero." in response.content
