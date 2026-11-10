from decimal import Decimal

import pytest

from sales import services
from sales.models import MenuItem, Order

POS = {"Owner": 200, "Manager": 200, "Cashier": 200, "Kitchen": 403, "Staff": 403}
KITCHEN = {"Owner": 200, "Manager": 200, "Kitchen": 200, "Cashier": 403, "Staff": 403}
MENU = {"Owner": 200, "Manager": 200, "Cashier": 403, "Kitchen": 403, "Staff": 403}


def pos_data(dish, qty="2", **overrides):
    data = {
        f"qty_{dish.pk}": qty,
        "order_type": "dine_in",
        "table_label": "T4",
        "payment_method": "cash",
        "amount_tendered": "1000",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", POS.items())
def test_pos_access_per_role(client_for, stocked_menu, role, status):
    assert client_for(role).get("/app/sales/pos/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", KITCHEN.items())
def test_kitchen_board_access_per_role(client_for, role, status):
    assert client_for(role).get("/app/sales/kitchen/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", MENU.items())
def test_menu_admin_access_per_role(client_for, role, status):
    assert client_for(role).get("/app/sales/menu/").status_code == status


@pytest.mark.django_db
def test_pos_checkout_creates_order_and_deducts_stock(client_for, stocked_menu):
    response = client_for("Cashier").post("/app/sales/pos/", pos_data(stocked_menu["dish"]))
    o = Order.objects.get()
    assert response.status_code == 302 and response.url == f"/app/sales/orders/{o.pk}/"
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == Decimal("9.6")


@pytest.mark.django_db
def test_pos_dine_in_requires_table(client_for, stocked_menu):
    response = client_for("Cashier").post(
        "/app/sales/pos/", pos_data(stocked_menu["dish"], table_label="")
    )
    assert response.status_code == 200 and not Order.objects.exists()


@pytest.mark.django_db
def test_pos_shows_stock_error_without_creating_order(client_for, stocked_menu):
    response = client_for("Cashier").post(
        "/app/sales/pos/", pos_data(stocked_menu["dish"], qty="60", amount_tendered="99999")
    )
    assert response.status_code == 200
    assert "Not enough stock" in response.content.decode()
    assert not Order.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "role,expected",
    [
        ("Manager", "voided"),
        ("Owner", "voided"),
        ("Cashier", "paid"),
        ("Kitchen", "paid"),
        ("Staff", "paid"),
    ],
)
def test_only_management_can_void(client_for, make_user, stocked_menu, role, expected):
    o = services.place_order(
        quantities={stocked_menu["dish"].pk: 1},
        cashier=make_user("Cashier"),
        order_type="takeaway",
        payment_method="card",
    )
    client_for(role).post(f"/app/sales/orders/{o.pk}/void/", {"reason": "test"})
    o.refresh_from_db()
    assert o.status == expected


@pytest.mark.django_db
def test_kitchen_can_advance_order(client_for, make_user, stocked_menu):
    o = services.place_order(
        quantities={stocked_menu["dish"].pk: 1},
        cashier=make_user("Cashier"),
        order_type="takeaway",
        payment_method="card",
    )
    client_for("Kitchen").post(f"/app/sales/kitchen/{o.pk}/advance/")
    o.refresh_from_db()
    assert o.kitchen_status == "preparing"


@pytest.mark.django_db
def test_manager_creates_menu_item_with_recipe(client_for, stocked_menu):
    data = {
        "category": stocked_menu["category"].pk,
        "name": "Fried rice",
        "description": "",
        "price": "150.00",
        "is_available": "on",
        "recipe-TOTAL_FORMS": "1",
        "recipe-INITIAL_FORMS": "0",
        "recipe-MIN_NUM_FORMS": "0",
        "recipe-MAX_NUM_FORMS": "1000",
        "recipe-0-inventory_item": stocked_menu["rice"].pk,
        "recipe-0-quantity": "0.3",
    }
    response = client_for("Manager").post("/app/sales/menu/new/", data)
    assert response.status_code == 302
    item = MenuItem.objects.get(name="Fried rice")
    assert item.recipe.get().quantity == Decimal("0.3")


@pytest.mark.django_db
def test_menu_price_must_be_positive(client_for, stocked_menu):
    data = {
        "category": stocked_menu["category"].pk,
        "name": "Free",
        "price": "0",
        "recipe-TOTAL_FORMS": "0",
        "recipe-INITIAL_FORMS": "0",
        "recipe-MIN_NUM_FORMS": "0",
        "recipe-MAX_NUM_FORMS": "1000",
    }
    response = client_for("Manager").post("/app/sales/menu/new/", data)
    assert response.status_code == 200
    assert not MenuItem.objects.filter(name="Free").exists()
