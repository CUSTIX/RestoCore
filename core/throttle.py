"""Small Postgres-backed rate limiter shared by every app.

    if throttle.is_limited("booking-ip", ip, limit=3, window=HOUR): ...
    throttle.record("booking-ip", ip)

Keys are plain strings (an IP, "username|ip", ...). Old events are pruned as new ones arrive.
"""

import datetime as dt
import ipaddress

from django.conf import settings
from django.utils import timezone

from core.models import ThrottleEvent

KEEP_FOR = dt.timedelta(days=2)  # longer than any window we use


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


def _key(key) -> str:
    return str(key if key is not None else "unknown")[:200]


def count(scope: str, key, window: dt.timedelta) -> int:
    since = timezone.now() - window
    return ThrottleEvent.objects.filter(scope=scope, key=_key(key), created_at__gte=since).count()


def is_limited(scope: str, key, *, limit: int, window: dt.timedelta) -> bool:
    return count(scope, key, window) >= limit


def record(scope: str, key) -> None:
    ThrottleEvent.objects.create(scope=scope, key=_key(key))
    ThrottleEvent.objects.filter(created_at__lt=timezone.now() - KEEP_FOR).delete()


def clear(scope: str, key) -> None:
    ThrottleEvent.objects.filter(scope=scope, key=_key(key)).delete()
