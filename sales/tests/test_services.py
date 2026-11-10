from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from inventory.services import InsufficientStock
from sales import services
from sales.models import Order

D = Decimal


@pytest.fixture
def cashier(make_user):
    return make_user("Cashier")


def order(stocked_menu, cashier, qty=2, **kwargs):
    params = {"order_type": "takeaway", "payment_method": "cash", "amount_tendered": D("500")}
    params.update(kwargs)
    return services.place_order(
        quantities={stocked_menu["dish"].pk: qty}, cashier=cashier, **params
    )


def test_order_prices_tax_and_change(stocked_menu, cashier, settings):
    settings.SALES_TAX_RATE = "0.12"
    o = order(stocked_menu, cashier, qty=2)
    assert o.subtotal == D("200.00") and o.tax == D("24.00") and o.total == D("224.00")
    assert o.change_due == D("276.00")
    assert o.lines.get().name == "Rice bowl"


def test_order_deducts_stock_in_same_transaction(stocked_menu, cashier):
    o = order(stocked_menu, cashier, qty=3)
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == D("9.4")  # 10 - 3 × 0.2
    assert stocked_menu["rice"].movements.filter(reference=o.stock_reference).exists()


def test_insufficient_stock_rolls_back_everything(stocked_menu, cashier):
    with pytest.raises(InsufficientStock):
        order(stocked_menu, cashier, qty=51, amount_tendered=D("99999"))  # needs 10.2 kg
    assert not Order.objects.exists()
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == D("10")


def test_cash_below_total_is_rejected(stocked_menu, cashier):
    with pytest.raises(ValidationError, match="at least"):
        order(stocked_menu, cashier, amount_tendered=D("1"))
    assert not Order.objects.exists()


def test_card_payment_needs_no_cash(stocked_menu, cashier):
    o = order(stocked_menu, cashier, payment_method="card", amount_tendered=None)
    assert o.amount_tendered == o.total and o.change_due == 0


def test_empty_order_rejected(stocked_menu, cashier):
    with pytest.raises(ValidationError, match="at least one"):
        services.place_order(
            quantities={stocked_menu["dish"].pk: 0},
            cashier=cashier,
            order_type="takeaway",
            payment_method="card",
        )


def test_unavailable_item_cannot_be_sold(stocked_menu, cashier):
    stocked_menu["dish"].is_available = False
    stocked_menu["dish"].save()
    with pytest.raises(ValidationError, match="no longer available"):
        order(stocked_menu, cashier)


def test_kitchen_flow_and_end(stocked_menu, cashier):
    o = order(stocked_menu, cashier)
    for expected in ("preparing", "ready", "served"):
        o = services.advance_kitchen_status(o)
        assert o.kitchen_status == expected
    with pytest.raises(ValidationError):
        services.advance_kitchen_status(o)


def test_void_returns_stock_when_not_served(stocked_menu, cashier, make_user):
    o = order(stocked_menu, cashier, qty=5, amount_tendered=D("1000"))
    services.void_order(o, user=make_user("Manager"), reason="Wrong order")
    o.refresh_from_db()
    stocked_menu["rice"].refresh_from_db()
    assert o.status == "voided" and o.kitchen_status == "cancelled"
    assert stocked_menu["rice"].quantity == D("10")


def test_void_after_served_keeps_stock_used(stocked_menu, cashier, make_user):
    o = order(stocked_menu, cashier, qty=5, amount_tendered=D("1000"))
    for _ in range(3):
        o = services.advance_kitchen_status(o)
    services.void_order(o, user=make_user("Manager"), reason="Complaint")
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == D("9")


def test_void_twice_and_void_without_reason_rejected(stocked_menu, cashier, make_user):
    manager = make_user("Manager")
    o = order(stocked_menu, cashier)
    with pytest.raises(ValidationError, match="reason"):
        services.void_order(o, user=manager, reason="  ")
    services.void_order(o, user=manager, reason="x")
    with pytest.raises(ValidationError, match="already voided"):
        services.void_order(o, user=manager, reason="x")


def test_price_snapshot_survives_menu_price_change(stocked_menu, cashier):
    o = order(stocked_menu, cashier, qty=1)
    stocked_menu["dish"].price = D("999")
    stocked_menu["dish"].save()
    assert o.lines.get().unit_price == D("100.00")
