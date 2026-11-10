from django.conf import settings
from django.urls import NoReverseMatch, reverse

from core.navigation import NAV_ITEMS
from core.roles import user_roles


def restocore(request):
    """Sidebar items the current user may see, their roles, and site-wide branding."""
    roles = user_roles(getattr(request, "user", None))
    nav = []
    for item in NAV_ITEMS:
        if not roles & set(item["roles"]):
            continue
        try:
            nav.append({**item, "href": reverse(item["url"])})
        except NoReverseMatch:  # module not installed yet
            continue
    return {
        "nav_items": nav,
        "current_roles": sorted(roles),
        "restaurant_name": settings.RESTAURANT_NAME,
    }
