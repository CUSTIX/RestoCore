from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.orders.models import Order, OrderItem
from apps.orders.services import InvalidOrderTransition, add_order_item, transition_order


@pytest.fixture
def cashier_user():
    user = get_user_model().objects.create_user(
        email="cashier-orders@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="cashier"))
    return user


@pytest.fixture
def ongoing_order():
    order = Order.objects.create()
    OrderItem.objects.create(
        order=order,
        item_name="Sample Meal",
        quantity=2,
        unit_price=Decimal("120.00"),
    )
    return order


@pytest.mark.django_db
def test_order_list_shows_total(client, cashier_user, ongoing_order):
    client.force_login(cashier_user)

    response = client.get(reverse("orders:home"))

    assert response.status_code == 200
    assert b"Sample Meal" not in response.content
    assert b"240.00" in response.content


@pytest.mark.django_db
def test_order_detail_shows_items_and_total(client, cashier_user, ongoing_order):
    client.force_login(cashier_user)

    response = client.get(reverse("orders:detail", args=[ongoing_order.pk]))

    assert response.status_code == 200
    assert b"Sample Meal" in response.content
    assert b"240.00" in response.content


@pytest.mark.django_db
def test_cashier_can_add_item_to_ongoing_order(client, cashier_user, ongoing_order):
    client.force_login(cashier_user)

    response = client.post(
        reverse("orders:add_item", args=[ongoing_order.pk]),
        {
            "item_name": "Drink",
            "quantity": 1,
            "unit_price": "45.50",
        },
    )

    assert response.status_code == 302
    assert OrderItem.objects.filter(order=ongoing_order, item_name="Drink").exists()
    assert AuditEvent.objects.filter(
        actor=cashier_user,
        action="orders.item_added",
        target_id=str(ongoing_order.pk),
    ).exists()


@pytest.mark.django_db
def test_order_item_cannot_be_added_after_service_started(cashier_user, ongoing_order):
    transition_order(
        order_id=ongoing_order.pk,
        new_status=Order.Status.SERVING,
        actor=cashier_user,
    )

    with pytest.raises(InvalidOrderTransition):
        add_order_item(
            order_id=ongoing_order.pk,
            item_name="Late item",
            quantity=1,
            unit_price=Decimal("10.00"),
            actor=cashier_user,
        )


@pytest.mark.django_db
def test_order_lifecycle_is_enforced_and_audited(cashier_user, ongoing_order):
    transition_order(
        order_id=ongoing_order.pk,
        new_status=Order.Status.SERVING,
        actor=cashier_user,
    )
    transition_order(
        order_id=ongoing_order.pk,
        new_status=Order.Status.SERVED,
        actor=cashier_user,
    )

    ongoing_order.refresh_from_db()
    assert ongoing_order.status == Order.Status.SERVED
    assert (
        AuditEvent.objects.filter(
            actor=cashier_user,
            action="orders.status_changed",
            target_id=str(ongoing_order.pk),
        ).count()
        == 2
    )


@pytest.mark.django_db
def test_invalid_order_transition_is_rejected(cashier_user, ongoing_order):
    with pytest.raises(InvalidOrderTransition):
        transition_order(
            order_id=ongoing_order.pk,
            new_status=Order.Status.SERVED,
            actor=cashier_user,
        )
