"""Customer self-ordering: a table QR code opens the menu, the customer gets a short code, and the
cashier charges it in the POS (which creates the real order and deducts stock)."""

import datetime as dt
import re
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from sales import services
from sales.models import MenuItem, Order, SelfOrder

D = Decimal
CASHIER_ROLES = {"Owner": 200, "Manager": 200, "Cashier": 200, "Kitchen": 403, "Staff": 403}
QR_ROLES = {"Owner": 200, "Manager": 200, "Cashier": 403, "Kitchen": 403, "Staff": 403}


def self_order(stocked_menu, qty=2, ip="203.0.113.5", **kwargs):
    params = {"order_type": "dine_in", "table_label": "5"}
    params.update(kwargs)
    return services.create_self_order(quantities={stocked_menu["dish"].pk: qty}, ip=ip, **params)


def charge(so, cashier, stocked_menu, qty=2, **kwargs):
    params = {
        "order_type": so.order_type,
        "table_label": so.table_label,
        "payment_method": "cash",
        "amount_tendered": D("1000"),
    }
    params.update(kwargs)
    return services.charge_self_order(
        so, quantities={stocked_menu["dish"].pk: qty}, cashier=cashier, **params
    )


# ---- Services -----------------------------------------------------------------------------


def test_self_order_is_priced_but_not_a_sale(stocked_menu, settings):
    settings.SALES_TAX_RATE = "0.12"
    so = self_order(stocked_menu, qty=2)
    assert so.status == SelfOrder.Status.PENDING
    assert (so.subtotal, so.tax, so.total) == (D("200.00"), D("24.00"), D("224.00"))
    assert re.fullmatch(f"[{services.CODE_ALPHABET}]{{5}}", so.code)
    assert so.lines.get().name == "Rice bowl"
    assert not Order.objects.exists()  # nothing charged
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == D("10")  # no stock moved


def test_takeaway_drops_the_table(stocked_menu):
    assert self_order(stocked_menu, order_type="takeaway", table_label="5").table_label == ""


def test_self_order_refuses_more_than_the_stock_can_make(stocked_menu):
    with pytest.raises(ValidationError, match="Rice bowl"):
        self_order(stocked_menu, qty=51)  # 51 × 0.2 kg > 10 kg
    assert not SelfOrder.objects.exists()


def test_self_order_refuses_unavailable_items(stocked_menu):
    MenuItem.objects.filter(pk=stocked_menu["dish"].pk).update(is_available=False)
    with pytest.raises(ValidationError):
        self_order(stocked_menu)


def test_self_orders_are_rate_limited_per_ip(stocked_menu, monkeypatch):
    monkeypatch.setattr(services, "SELF_ORDERS_PER_IP_PER_HOUR", 2)
    self_order(stocked_menu, ip="198.51.100.1")
    self_order(stocked_menu, ip="198.51.100.1")
    with pytest.raises(ValidationError, match="Too many"):
        self_order(stocked_menu, ip="198.51.100.1")
    self_order(stocked_menu, ip="198.51.100.2")  # another visitor is fine


def test_code_already_open_is_drawn_again(stocked_menu, monkeypatch):
    first = self_order(stocked_menu)
    codes = iter([first.code, first.code, "XY347"])
    monkeypatch.setattr(services, "new_code", lambda: next(codes))
    assert self_order(stocked_menu).code == "XY347"


def test_old_unpaid_orders_expire_and_free_their_code(stocked_menu):
    so = self_order(stocked_menu)
    SelfOrder.objects.filter(pk=so.pk).update(
        created_at=timezone.now() - services.SELF_ORDER_TTL - dt.timedelta(minutes=1)
    )
    assert services.expire_stale_self_orders() == 1
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.EXPIRED


def test_normalize_code_accepts_what_the_cashier_types():
    assert services.normalize_code(" #k7m-4p ") == "K7M4P"


def test_charging_creates_the_order_and_deducts_stock(stocked_menu, make_user):
    so = self_order(stocked_menu, qty=2)
    order = charge(so, make_user("Cashier"), stocked_menu, qty=3)  # customer added one more
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.PAID and so.order == order
    assert order.checkout_token == so.token and order.table_label == "5"
    assert order.lines.get().quantity == 3
    stocked_menu["rice"].refresh_from_db()
    assert stocked_menu["rice"].quantity == D("9.4")


def test_charging_twice_returns_the_same_order(stocked_menu, make_user):
    so = self_order(stocked_menu)
    cashier = make_user("Cashier")
    assert charge(so, cashier, stocked_menu) == charge(so, cashier, stocked_menu)
    assert Order.objects.count() == 1


def test_a_cancelled_order_cannot_be_charged(stocked_menu, make_user):
    so = services.cancel_self_order(self_order(stocked_menu))
    with pytest.raises(ValidationError, match="cancelled"):
        charge(so, make_user("Cashier"), stocked_menu)
    assert not Order.objects.exists()


def test_failed_payment_leaves_the_customer_order_open(stocked_menu, make_user):
    so = self_order(stocked_menu)
    with pytest.raises(ValidationError):
        charge(so, make_user("Cashier"), stocked_menu, amount_tendered=D("1"))
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.PENDING and so.order is None


def test_a_paid_order_cannot_be_cancelled(stocked_menu, make_user):
    so = self_order(stocked_menu)
    charge(so, make_user("Cashier"), stocked_menu)
    with pytest.raises(ValidationError):
        services.cancel_self_order(so)


def test_qr_svg_is_an_inline_svg():
    svg = services.qr_svg("https://example.com/order/?table=5")
    assert svg.startswith("<svg") and "<path" in svg and "<?xml" not in svg


# ---- Customer pages (no login) ------------------------------------------------------------


def test_order_page_is_public_and_prefills_the_table(client, stocked_menu):
    response = client.get("/order/?table=12")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Table 12" in html and 'value="12"' in html
    assert re.search(r'value="dine_in"\s+checked', html)
    assert "Rice bowl" in html


def test_order_page_ignores_a_bad_table_value(client, stocked_menu):
    response = client.get("/order/?table=<script>x</script>")
    assert response.status_code == 200 and "<script>x" not in response.content.decode()
    assert re.search(r'value="takeaway"\s+checked', response.content.decode())


def test_customer_places_an_order_and_sees_the_code(client, stocked_menu):
    dish = stocked_menu["dish"]
    response = client.post(
        "/order/", {f"qty_{dish.pk}": "2", "order_type": "dine_in", "table_label": "7"}
    )
    so = SelfOrder.objects.get()
    assert response.status_code == 302 and response.url == f"/order/{so.token}/"
    assert so.table_label == "7" and not Order.objects.exists()
    page = client.get(response.url).content.decode()
    assert so.code in page and "Show this at the counter" in page
    assert "data-auto-reload" in page  # waiting: the page refreshes itself
    # Back on the menu, the customer is reminded of their open order.
    assert so.code in client.get("/order/").content.decode()


def test_customer_order_needs_a_dish(client, stocked_menu):
    response = client.post("/order/", {"order_type": "takeaway"})
    assert response.status_code == 200 and not SelfOrder.objects.exists()
    assert "Add at least one item" in response.content.decode()


def test_dine_in_customer_order_needs_a_table(client, stocked_menu):
    dish = stocked_menu["dish"]
    response = client.post("/order/", {f"qty_{dish.pk}": "1", "order_type": "dine_in"})
    assert response.status_code == 200 and not SelfOrder.objects.exists()


def test_status_page_for_unknown_order_is_404(client, db):
    assert client.get("/order/00000000-0000-4000-8000-000000000000/").status_code == 404


def test_customer_can_cancel_an_unpaid_order(client, stocked_menu):
    so = self_order(stocked_menu)
    response = client.post(f"/order/{so.token}/cancel/")
    assert response.status_code == 302
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.CANCELLED


def test_customer_cannot_cancel_after_paying(client, stocked_menu, make_user):
    so = self_order(stocked_menu)
    charge(so, make_user("Cashier"), stocked_menu)
    client.post(f"/order/{so.token}/cancel/")
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.PAID


def test_status_page_follows_the_kitchen(client, stocked_menu, make_user):
    so = self_order(stocked_menu)
    order = charge(so, make_user("Cashier"), stocked_menu)
    assert "next in the kitchen" in client.get(f"/order/{so.token}/").content.decode()
    Order.objects.filter(pk=order.pk).update(kitchen_status="ready")
    page = client.get(f"/order/{so.token}/").content.decode()
    assert "Ready!" in page and order.number in page
    Order.objects.filter(pk=order.pk).update(kitchen_status="served")
    assert "data-auto-reload" not in client.get(f"/order/{so.token}/").content.decode()


# ---- Cashier side -------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", CASHIER_ROLES.items())
def test_customer_orders_access_per_role(client_for, role, status):
    assert client_for(role).get("/app/sales/self-orders/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", QR_ROLES.items())
def test_table_qr_access_per_role(client_for, role, status):
    assert client_for(role).get("/app/sales/table-qr/").status_code == status


def test_waiting_list_shows_open_orders_only(client_for, stocked_menu):
    waiting = self_order(stocked_menu)
    gone = services.cancel_self_order(self_order(stocked_menu))
    html = client_for("Cashier").get("/app/sales/self-orders/").content.decode()
    assert waiting.code in html and gone.code not in html


def test_search_by_code_opens_the_pos(client_for, stocked_menu):
    so = self_order(stocked_menu)
    response = client_for("Cashier").get("/app/sales/self-orders/", {"code": f"#{so.code.lower()}"})
    assert response.status_code == 302
    assert response.url == f"/app/sales/pos/?self_order={so.token}"


def test_search_for_an_unknown_code_says_so(client_for, db):
    response = client_for("Cashier").get("/app/sales/self-orders/", {"code": "ZZZZZ"}, follow=True)
    assert response.status_code == 200 and "No open order with code ZZZZZ" in (
        response.content.decode()
    )


def test_pos_opens_with_the_customers_items(client_for, stocked_menu):
    so = self_order(stocked_menu, qty=3)
    html = client_for("Cashier").get(f"/app/sales/pos/?self_order={so.token}").content.decode()
    dish = stocked_menu["dish"]
    assert f"Customer order {so.code}" in html
    assert re.search(rf'name="qty_{dish.pk}"[^>]*\s+value="3"', html)
    assert f'value="{so.token}"' in html  # self_order + checkout token


def test_pos_charges_the_customer_order_once(client_for, stocked_menu):
    so = self_order(stocked_menu, qty=2)
    client = client_for("Cashier")
    data = {
        f"qty_{stocked_menu['dish'].pk}": "2",
        "order_type": "dine_in",
        "table_label": "5",
        "payment_method": "cash",
        "amount_tendered": "500",
        "checkout_token": str(so.token),
        "self_order": str(so.token),
    }
    first = client.post("/app/sales/pos/", data)
    second = client.post("/app/sales/pos/", data)  # double click
    order = Order.objects.get()
    assert first.url == second.url == f"/app/sales/orders/{order.pk}/"
    so.refresh_from_db()
    assert so.status == SelfOrder.Status.PAID and so.order == order
    # Opening it again goes to the receipt instead of a second charge screen.
    response = client.get(f"/app/sales/pos/?self_order={so.token}")
    assert response.status_code == 302 and response.url == f"/app/sales/orders/{order.pk}/"


def test_pos_refuses_a_cancelled_customer_order(client_for, stocked_menu):
    so = services.cancel_self_order(self_order(stocked_menu))
    response = client_for("Cashier").get(f"/app/sales/pos/?self_order={so.token}")
    assert response.status_code == 302 and response.url == "/app/sales/self-orders/"


@pytest.mark.django_db
@pytest.mark.parametrize("role,allowed", [("Cashier", True), ("Kitchen", False)])
def test_staff_cancel_per_role(client_for, stocked_menu, role, allowed):
    so = self_order(stocked_menu)
    response = client_for(role).post(f"/app/sales/self-orders/{so.pk}/cancel/")
    so.refresh_from_db()
    assert (so.status == SelfOrder.Status.CANCELLED) is allowed
    assert response.status_code == (302 if allowed else 403)


def test_table_qr_page_makes_a_code_per_table(client_for, db):
    html = client_for("Manager").get("/app/sales/table-qr/", {"tables": "1-3, Patio"}).content
    html = html.decode()
    assert html.count("<svg") >= 5  # counter + 3 tables + patio (+ icons)
    assert "http://testserver/order/?table=Patio" in html
    assert "Table 3" in html and "Table 4" not in html


def test_table_qr_page_rejects_bad_input(client_for, db):
    response = client_for("Manager").get("/app/sales/table-qr/", {"tables": "1-500"})
    assert response.status_code == 200 and "at most" in response.content.decode()


def test_pos_leaves_out_a_dish_that_sold_out_since(client_for, stocked_menu):
    """Its POS input is disabled when sold out: prefilling it would make Charge impossible."""
    from inventory.models import InventoryItem

    so = self_order(stocked_menu, qty=2)
    InventoryItem.objects.filter(pk=stocked_menu["rice"].pk).update(quantity=D("0"))
    html = client_for("Cashier").get(f"/app/sales/pos/?self_order={so.token}").content.decode()
    dish = stocked_menu["dish"]
    assert "2 × Rice bowl</strong> is sold out" in html
    assert re.search(rf'name="qty_{dish.pk}"[^>]*\s+value="0"', html)


def test_paid_status_shows_what_was_charged(client, stocked_menu, make_user):
    so = self_order(stocked_menu, qty=2)
    order = charge(so, make_user("Cashier"), stocked_menu, qty=3)  # changed at the counter
    page = client.get(f"/order/{so.token}/").content.decode()
    assert "3 × Rice bowl" in page and "2 × Rice bowl" not in page
    assert f"{order.total:,.2f}" in page and "changed at the counter" in page


def test_voided_order_shows_no_progress_steps(client, stocked_menu, make_user):
    so = self_order(stocked_menu)
    order = charge(so, make_user("Cashier"), stocked_menu)
    services.void_order(order, user=make_user("Manager"), reason="Wrong table")
    page = client.get(f"/order/{so.token}/").content.decode()
    assert "This order was cancelled" in page and "order-steps" not in page
    assert "data-auto-reload" not in page
