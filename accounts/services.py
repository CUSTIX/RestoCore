import datetime as dt

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction

from core import throttle
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


# --- Sign-in throttling ------------------------------------------------------------------------
# Slows down password guessing without letting a stranger lock real users out:
#   - per (username, IP): 5 failures in 15 minutes locks that pair for the rest of the window;
#   - per IP: 30 failures in 15 minutes (password spraying across many usernames) locks that IP.
# A different person on another IP can still sign in to the same account.

LOGIN_WINDOW = dt.timedelta(minutes=15)
MAX_FAILURES_PER_USER_IP = 5
MAX_FAILURES_PER_IP = 30
_USER_IP, _IP = "login-user-ip", "login-ip"


def _pair(username: str, ip: str | None) -> str:
    return f"{(username or '').strip().lower()[:150]}|{ip or '?'}"


def is_login_locked(username: str, ip: str | None) -> bool:
    if throttle.is_limited(
        _USER_IP, _pair(username, ip), limit=MAX_FAILURES_PER_USER_IP, window=LOGIN_WINDOW
    ):
        return True
    # No usable IP: don't pool everyone into one shared "unknown" bucket.
    return ip is not None and throttle.is_limited(
        _IP, ip, limit=MAX_FAILURES_PER_IP, window=LOGIN_WINDOW
    )


def record_login_failure(username: str, ip: str | None) -> None:
    throttle.record(_USER_IP, _pair(username, ip))
    if ip is not None:
        throttle.record(_IP, ip)


def clear_login_failures(username: str, ip: str | None) -> None:
    throttle.clear(_USER_IP, _pair(username, ip))
