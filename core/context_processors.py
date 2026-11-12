import os

from django.conf import settings
from django.urls import NoReverseMatch, reverse

from core.navigation import NAV_ITEMS
from core.roles import user_roles


def restocore(request):
    """Sidebar items the current user may see, their roles, and site-wide branding."""
    roles = user_roles(getattr(request, "user", None))
    nav, groups = [], {}
    for item in NAV_ITEMS:
        if not roles & set(item["roles"]):
            continue
        try:
            entry = {**item, "href": reverse(item["url"])}
        except NoReverseMatch:  # module not installed yet
            continue
        nav.append(entry)
        groups.setdefault(item["group"], []).append(entry)
    return {
        "nav_items": nav,
        "nav_groups": list(groups.items()),
        "current_roles": sorted(roles),
        "restaurant_name": settings.RESTAURANT_NAME,
        "currency": settings.CURRENCY_SYMBOL,
        # Local dev, or a public demo that opts in with DEMO_MODE (data resets on each start).
        "show_demo_logins": settings.DEBUG or settings.DEMO_MODE,
        "demo_public": settings.DEMO_MODE and not settings.DEBUG,
        "demo_password": os.environ.get("DEMO_PASSWORD", "restocore-demo")
        if settings.DEBUG or settings.DEMO_MODE
        else "",
    }
