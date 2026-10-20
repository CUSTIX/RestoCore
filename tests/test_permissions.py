import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from django_otp import DEVICE_ID_SESSION_KEY
from django_otp.plugins.otp_totp.models import TOTPDevice

from apps.accounts.roles import ROLE_PERMISSIONS

ROUTES = {
    "core:workspace": "core.access_internal",
    "bookings:home": "bookings.access_bookings",
    "orders:home": "orders.access_orders",
    "inventory:home": "inventory.access_inventory",
    "staff:home": "staff.access_staff",
    "payroll:home": "payroll.access_payroll",
    "pos:home": "pos.access_pos",
    "reports:home": "reports.access_reports",
}


@pytest.mark.django_db
def test_role_matrix_references_existing_permissions():
    from django.contrib.auth.models import Permission

    existing = {
        f"{permission.content_type.app_label}.{permission.codename}"
        for permission in Permission.objects.select_related("content_type")
    }
    referenced = set().union(*ROLE_PERMISSIONS.values())
    assert referenced <= existing


@pytest.mark.django_db
def test_anonymous_internal_route_redirects_to_login(client):
    response = client.get(reverse("core:workspace"))
    assert response.status_code == 302
    assert reverse("accounts:login") in response.url


@pytest.mark.django_db
@pytest.mark.parametrize("role_name", ROLE_PERMISSIONS)
def test_permission_matrix_for_module_routes(client, role_name):
    user = get_user_model().objects.create_user(
        email=f"{role_name}@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name=role_name))
    client.force_login(user)

    if role_name in {"owner", "payroll"}:
        device = TOTPDevice.objects.create(
            user=user,
            name="Test authenticator",
            confirmed=True,
        )
        session = client.session
        session[DEVICE_ID_SESSION_KEY] = device.persistent_id
        session.save()

    expected_permissions = ROLE_PERMISSIONS[role_name]
    for route_name, permission in ROUTES.items():
        response = client.get(reverse(route_name))
        expected_status = 200 if permission in expected_permissions else 403
        assert response.status_code == expected_status, (
            f"{role_name=} {route_name=} {permission=} returned {response.status_code}"
        )


@pytest.mark.django_db
def test_navigation_hides_unauthorized_modules(client):
    user = get_user_model().objects.create_user(
        email="cashier-nav@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name="cashier"))
    client.force_login(user)

    response = client.get(reverse("core:workspace"))

    assert response.status_code == 200
    assert b"POS" in response.content
    assert b"Payroll" not in response.content
