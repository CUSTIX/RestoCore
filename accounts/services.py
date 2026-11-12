import datetime as dt
import ipaddress

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.utils import timezone

from accounts.models import LoginFailure
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


def client_ip(request) -> str | None:
    """The visitor's IP. Behind a proxy, read only the header that proxy sets and overwrites
    (settings.CLIENT_IP_HEADER, e.g. Cloudflare's CF-Connecting-IP); never trust X-Forwarded-For
    blindly, because callers can forge it."""
    header = getattr(settings, "CLIENT_IP_HEADER", "")
    value = (request.META.get(header, "") if header else "") or request.META.get("REMOTE_ADDR", "")
    value = value.split(",")[0].strip()
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _recent_failures(**filters):
    since = timezone.now() - LOGIN_WINDOW
    return LoginFailure.objects.filter(created_at__gte=since, **filters)


def is_login_locked(username: str, ip: str | None) -> bool:
    username = (username or "").strip().lower()
    if _recent_failures(username=username, ip_address=ip).count() >= MAX_FAILURES_PER_USER_IP:
        return True
    return ip is not None and _recent_failures(ip_address=ip).count() >= MAX_FAILURES_PER_IP


def record_login_failure(username: str, ip: str | None) -> None:
    LoginFailure.objects.create(username=(username or "").strip().lower()[:150], ip_address=ip)
    # Housekeeping: old rows are useless once outside the window.
    LoginFailure.objects.filter(created_at__lt=timezone.now() - dt.timedelta(days=1)).delete()


def clear_login_failures(username: str, ip: str | None) -> None:
    LoginFailure.objects.filter(username=(username or "").strip().lower(), ip_address=ip).delete()
