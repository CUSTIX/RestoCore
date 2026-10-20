import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser, Group

from apps.accounts.security import is_mfa_verified, requires_mfa


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("group_name", "expected"),
    [
        ("owner", True),
        ("payroll", True),
        ("manager", False),
        ("cashier", False),
        ("kitchen", False),
        ("waiter", False),
    ],
)
def test_mfa_policy_by_role(group_name, expected):
    user = get_user_model().objects.create_user(
        email=f"{group_name}-mfa@example.com",
        password="test-only-password",
    )
    user.groups.add(Group.objects.get(name=group_name))

    assert requires_mfa(user) is expected


@pytest.mark.django_db
def test_superuser_requires_mfa():
    user = get_user_model().objects.create_superuser(
        email="superuser@example.com",
        password="test-only-password",
    )

    assert requires_mfa(user) is True


def test_anonymous_user_does_not_require_mfa():
    assert requires_mfa(AnonymousUser()) is False


def test_unverified_user_is_not_mfa_verified():
    user = AnonymousUser()
    assert is_mfa_verified(user) is False
