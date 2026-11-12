from decimal import Decimal

import pytest

from inventory import services
from inventory.models import InventoryItem

VIEW = {"Owner": 200, "Manager": 200, "Kitchen": 200, "Cashier": 403, "Staff": 403}
MANAGE = {"Owner": 302, "Manager": 302, "Kitchen": 403, "Cashier": 403, "Staff": 403}


@pytest.fixture
def item(db):
    return services.create_item(
        name="Milk",
        unit="l",
        quantity=Decimal("5"),
        reorder_level=Decimal("2"),
        cost_per_unit=Decimal("90"),
    )


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", VIEW.items())
def test_inventory_list_access_per_role(client_for, item, role, status):
    assert client_for(role).get("/app/inventory/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", MANAGE.items())
def test_create_item_access_per_role(client_for, role, status):
    data = {
        "name": "Butter",
        "unit": "kg",
        "quantity": "2",
        "reorder_level": "1",
        "cost_per_unit": "400",
        "is_active": "on",
    }
    response = client_for(role).post("/app/inventory/new/", data)
    assert response.status_code == status
    assert InventoryItem.objects.filter(name="Butter").exists() == (status == 302)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,status", {**VIEW, "Owner": 302, "Manager": 302, "Kitchen": 302}.items()
)
def test_kitchen_and_management_can_receive_stock(client_for, item, role, status):
    response = client_for(role).post(
        f"/app/inventory/{item.pk}/", {"action": "receive", "quantity": "3", "note": ""}
    )
    assert response.status_code == status
    item.refresh_from_db()
    assert item.quantity == (Decimal("8") if status == 302 else Decimal("5"))


@pytest.mark.django_db
def test_waste_more_than_on_hand_shows_error(client_for, item):
    response = client_for("Kitchen").post(
        f"/app/inventory/{item.pk}/", {"action": "waste", "quantity": "50", "note": ""}
    )
    assert response.status_code == 200
    assert "below zero" in response.content.decode()


@pytest.mark.django_db
def test_low_stock_filter(client_for, item):
    services.create_item(
        name="Plenty", unit="kg", quantity=Decimal("100"), reorder_level=Decimal("1")
    )
    services.record_count(item_id=item.pk, counted=Decimal("1"))
    html = client_for("Manager").get("/app/inventory/?low=on").content.decode()
    assert "Milk" in html and "Plenty" not in html


@pytest.mark.django_db
def test_unit_is_locked_once_stock_history_exists(client_for, stocked_menu):
    """kg -> g would silently turn 0.2 kg of rice per dish into 0.2 g."""
    from django.core.exceptions import ValidationError

    from inventory import services

    rice = stocked_menu["rice"]  # has an opening-stock movement
    client = client_for("Manager")
    form_html = client.get(f"/app/inventory/{rice.pk}/edit/").content.decode()
    assert "Fixed once stock has been recorded" in form_html
    client.post(
        f"/app/inventory/{rice.pk}/edit/",
        {
            "name": "Rice",
            "unit": "g",
            "reorder_level": "2",
            "cost_per_unit": "50",
            "is_active": "on",
        },
    )
    rice.refresh_from_db()
    assert rice.unit == "kg"
    rice.unit = "g"  # what a ModelForm does to the instance before the service runs
    with pytest.raises(ValidationError, match="unit can't change"):
        services.update_item(rice, unit="g", name="Rice")


@pytest.mark.django_db
def test_unit_can_change_while_an_item_has_no_history(client_for):
    from decimal import Decimal

    from inventory import services

    item = services.create_item(
        name="Tea", unit="kg", quantity=Decimal("0"), reorder_level=0, cost_per_unit=1
    )
    services.update_item(item, unit="g", name="Tea")
    item.refresh_from_db()
    assert item.unit == "g"
