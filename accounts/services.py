from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from core.roles import ALL_ROLES


def ensure_role_groups() -> None:
    """Create the five role groups if they are missing (idempotent)."""
    for name in ALL_ROLES:
        Group.objects.get_or_create(name=name)


@transaction.atomic
def create_user_with_role(
    *,
    username: str,
    password: str,
    role: str,
    first_name: str = "",
    last_name: str = "",
    email: str = "",
):
    if role not in ALL_ROLES:
        raise ValueError(f"Unknown role: {role}")
    user = get_user_model().objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
    )
    user.groups.add(Group.objects.get(name=role))
    return user


@transaction.atomic
def set_user_role(user, role: str) -> None:
    """Replace the user's role groups with exactly one role."""
    if role not in ALL_ROLES:
        raise ValueError(f"Unknown role: {role}")
    user.groups.remove(*Group.objects.filter(name__in=ALL_ROLES))
    user.groups.add(Group.objects.get(name=role))
