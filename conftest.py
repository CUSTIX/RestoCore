"""Shared pytest fixtures for every RestoCore app."""

import datetime as dt
from decimal import Decimal

import pytest
from django.utils import timezone

from accounts.services import create_user_with_role
from core.roles import ALL_ROLES

PASSWORD = "test-pass-123!"


@pytest.fixture
def make_user(db):
    counter = {"n": 0}

    def _make(role: str | None = None, **kwargs):
        counter["n"] += 1
        username = kwargs.pop("username", f"{(role or 'norole').lower()}{counter['n']}")
        if role:
            return create_user_with_role(username=username, password=PASSWORD, role=role, **kwargs)
        from django.contrib.auth import get_user_model

        return get_user_model().objects.create_user(username=username, password=PASSWORD)

    return _make


@pytest.fixture
def client_for(client, make_user):
    """client_for("Manager") → a test client logged in as a new user with that role."""

    def _client(role: str | None = None, user=None):
        user = user or make_user(role)
        client.force_login(user)
        client.user = user
        return client

    return _client


@pytest.fixture
def make_employee(make_user):
    from staff.models import Employee

    def _make(role="Staff", rate=Decimal("100"), user=None, **kwargs):
        user = user or make_user(role)
        return Employee.objects.create(
            user=user,
            position=kwargs.pop("position", role),
            hourly_rate=rate,
            hire_date=kwargs.pop("hire_date", dt.date(2024, 1, 1)),
            **kwargs,
        )

    return _make


@pytest.fixture
def stocked_menu(db):
    """One inventory item, one menu item that uses 0.2 of it, and 10 units on hand."""
    from inventory import services as inv
    from sales.models import MenuCategory, MenuItem, RecipeLine

    rice = inv.create_item(
        name="Rice",
        unit="kg",
        quantity=Decimal("10"),
        reorder_level=Decimal("2"),
        cost_per_unit=Decimal("50"),
    )
    cat = MenuCategory.objects.create(name="Mains")
    dish = MenuItem.objects.create(category=cat, name="Rice bowl", price=Decimal("100.00"))
    RecipeLine.objects.create(menu_item=dish, inventory_item=rice, quantity=Decimal("0.2"))
    return {"rice": rice, "dish": dish, "category": cat}


@pytest.fixture
def tomorrow():
    return timezone.localdate() + dt.timedelta(days=1)


ROLES = ALL_ROLES
