from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.orders.models import Order, OrderItem


@pytest.mark.django_db
def test_order_starts_ongoing():
    order = Order.objects.create()

    assert order.status == Order.Status.ONGOING


@pytest.mark.django_db
def test_order_item_line_total_uses_decimal_money():
    order = Order.objects.create()
    item = OrderItem.objects.create(
        order=order,
        item_name="Sample dish",
        quantity=3,
        unit_price=Decimal("99.95"),
    )

    assert item.line_total == Decimal("299.85")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("quantity", "unit_price"),
    [
        (0, Decimal("10.00")),
        (1, Decimal("-0.01")),
    ],
)
def test_order_item_rejects_invalid_quantity_or_price(quantity, unit_price):
    order = Order.objects.create()

    with pytest.raises(IntegrityError), transaction.atomic():
        OrderItem.objects.create(
            order=order,
            item_name="Invalid line",
            quantity=quantity,
            unit_price=unit_price,
        )
