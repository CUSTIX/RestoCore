"""Every /app/ URL against every role: the role a view declares in `allowed_roles` gets in, every
other role is refused with 403, for GET and POST. Driven by the real URLconf, so a new view that
forgets its role check (or declares one it does not enforce) fails here with no test written."""

import pytest
from django.urls import resolve

from core.mixins import RoleRequiredMixin
from core.roles import ALL_ROLES
from core.tests.test_access_guard import STAFF


def _view_class(url):
    return getattr(resolve(url).func, "view_class", None)


def test_every_staff_url_is_a_role_checked_view():
    """No function views or ad-hoc checks under /app/: they are the ones that get forgotten."""
    unchecked = [u for u in STAFF if not issubclass(_view_class(u) or object, RoleRequiredMixin)]
    assert not unchecked, f"Not RoleRequiredMixin views: {unchecked}"


def test_every_staff_view_declares_who_may_use_it():
    undeclared = [u for u in STAFF if not _view_class(u).allowed_roles]
    assert not undeclared, f"Empty allowed_roles (nobody could open them): {undeclared}"


CASES = [(url, role, method) for url in STAFF for role in ALL_ROLES for method in ("get", "post")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,role,method", CASES, ids=[f"{m.upper()} {u} as {r}" for u, r, m in CASES]
)
def test_each_role_gets_exactly_the_access_its_view_declares(
    client_for, make_employee, url, role, method
):
    # An employee profile, not just a role: some views (the clock) refuse a user without one for
    # a reason that has nothing to do with roles.
    client = client_for(role, user=make_employee(role=role).user)
    status = getattr(client, method)(url).status_code
    if role in _view_class(url).allowed_roles:
        assert status != 403, f"{role} is declared allowed but was refused"
    else:
        assert status == 403, f"{role} should be refused but got {status}"
