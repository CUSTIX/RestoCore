from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.orders.models import Order, OrderItem
from apps.pos.models import Payment
from apps.pos.services import InvalidPayment, take_cash_payment


@pytest.fixture
def cashier_user():
    user = get_user_model().objects.create_user(
        email="cashier-pos@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="cashier"))
    return user


@pytest.fixture
def priced_order():
    order = Order.objects.create()
    OrderItem.objects.create(
        order=order,
        item_name="Rice Bowl",
        quantity=2,
        unit_price=Decimal("125.00"),
    )
    return order


@pytest.mark.django_db
def test_cashier_page_creates_order_with_first_item(client, cashier_user):
    client.force_login(cashier_user)

    response = client.post(
        reverse("pos:home"),
        {
            "item_name": "Noodles",
            "quantity": 2,
            "unit_price": "95.50",
        },
    )

    order = Order.objects.get()
    item = order.items.get()
    assert response.status_code == 302
    assert response.url == reverse("orders:detail", args=[order.pk])
    assert item.item_name == "Noodles"
    assert item.quantity == 2
    assert item.unit_price == Decimal("95.50")
    assert AuditEvent.objects.filter(
        actor=cashier_user,
        action="pos.order_created",
        target_id=str(order.pk),
    ).exists()


@pytest.mark.django_db
def test_cash_payment_records_snapshot_change_and_audit(cashier_user, priced_order):
    payment = take_cash_payment(
        order_id=priced_order.pk,
        amount_tendered=Decimal("300.00"),
        actor=cashier_user,
    )

    assert payment.amount_due == Decimal("250.00")
    assert payment.amount_tendered == Decimal("300.00")
    assert payment.change_due == Decimal("50.00")
    assert payment.receipt_number.startswith("RC-")
    assert AuditEvent.objects.filter(
        actor=cashier_user,
        action="pos.payment_taken",
        target_id=str(priced_order.pk),
    ).exists()


@pytest.mark.django_db
def test_cash_payment_rejects_underpayment(cashier_user, priced_order):
    with pytest.raises(InvalidPayment, match="less than"):
        take_cash_payment(
            order_id=priced_order.pk,
            amount_tendered=Decimal("249.99"),
            actor=cashier_user,
        )

    assert not Payment.objects.filter(order=priced_order).exists()


@pytest.mark.django_db
def test_cash_payment_rejects_duplicate_payment(cashier_user, priced_order):
    take_cash_payment(
        order_id=priced_order.pk,
        amount_tendered=Decimal("250.00"),
        actor=cashier_user,
    )

    with pytest.raises(InvalidPayment, match="already paid"):
        take_cash_payment(
            order_id=priced_order.pk,
            amount_tendered=Decimal("250.00"),
            actor=cashier_user,
        )


@pytest.mark.django_db
def test_cash_payment_rejects_cancelled_order(cashier_user, priced_order):
    priced_order.status = Order.Status.CANCELLED
    priced_order.save(update_fields=["status"])

    with pytest.raises(InvalidPayment, match="Cancelled"):
        take_cash_payment(
            order_id=priced_order.pk,
            amount_tendered=Decimal("250.00"),
            actor=cashier_user,
        )


@pytest.mark.django_db
def test_checkout_and_receipt_pages_work(client, cashier_user, priced_order):
    client.force_login(cashier_user)

    checkout = client.get(reverse("pos:checkout", args=[priced_order.pk]))
    assert checkout.status_code == 200
    assert b"250.00" in checkout.content

    response = client.post(
        reverse("pos:checkout", args=[priced_order.pk]),
        {"amount_tendered": "300.00"},
    )
    payment = Payment.objects.get(order=priced_order)

    assert response.status_code == 302
    assert response.url == reverse("pos:receipt", args=[payment.pk])

    receipt = client.get(response.url)
    assert receipt.status_code == 200
    assert payment.receipt_number.encode() in receipt.content
    assert b"50.00" in receipt.content


@pytest.mark.django_db
def test_pay_route_redirects_existing_payment_to_receipt(
    client,
    cashier_user,
    priced_order,
):
    client.force_login(cashier_user)
    payment = take_cash_payment(
        order_id=priced_order.pk,
        amount_tendered=Decimal("250.00"),
        actor=cashier_user,
    )

    response = client.get(reverse("pos:pay", args=[priced_order.pk]))

    assert response.status_code == 302
    assert response.url == reverse("pos:receipt", args=[payment.pk])
