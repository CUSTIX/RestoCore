"""The five RestoCore roles. Each role is a Django Group of the same name."""

OWNER = "Owner"
MANAGER = "Manager"
CASHIER = "Cashier"
KITCHEN = "Kitchen"
STAFF = "Staff"

ALL_ROLES = (OWNER, MANAGER, CASHIER, KITCHEN, STAFF)
MANAGEMENT = (OWNER, MANAGER)


def user_roles(user) -> set[str]:
    """Role names for a user. Superusers count as Owner. Cached per request object."""
    if not user or not user.is_authenticated:
        return set()
    cached = getattr(user, "_restocore_roles", None)
    if cached is not None:
        return cached
    roles = set(user.groups.filter(name__in=ALL_ROLES).values_list("name", flat=True))
    if user.is_superuser:
        roles.add(OWNER)
    user._restocore_roles = roles
    return roles


def has_role(user, *roles: str) -> bool:
    return bool(user_roles(user) & set(roles))
