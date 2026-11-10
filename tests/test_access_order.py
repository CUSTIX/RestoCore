"""Role checks must run before any object lookup, so outsiders cannot probe which ids exist."""

import pytest

DETAIL_URLS = [
    ("/app/bookings/999999/edit/", "Cashier"),
    ("/app/inventory/999999/", "Staff"),
    ("/app/inventory/999999/edit/", "Kitchen"),
    ("/app/staff/employees/999999/edit/", "Cashier"),
    ("/app/staff/shifts/999999/edit/", "Staff"),
    ("/app/sales/menu/999999/edit/", "Cashier"),
    ("/app/payroll/periods/999999/", "Manager"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("url,role", DETAIL_URLS)
def test_wrong_role_gets_403_not_404_for_missing_object(client_for, url, role):
    assert client_for(role).get(url).status_code == 403


@pytest.mark.django_db
@pytest.mark.parametrize("url,role", DETAIL_URLS)
def test_anonymous_gets_login_redirect_not_404(client, url, role):
    response = client.get(url)
    assert response.status_code == 302 and "/accounts/login/" in response.url
