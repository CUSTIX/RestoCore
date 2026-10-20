from .navigation import NAVIGATION_ITEMS


def internal_navigation(request):
    """Expose only navigation destinations the current user may access."""

    if not request.user.is_authenticated:
        return {"navigation_items": ()}

    return {
        "navigation_items": tuple(
            item for item in NAVIGATION_ITEMS if request.user.has_perm(item["permission"])
        )
    }
