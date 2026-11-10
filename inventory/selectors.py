from django.db.models import F, QuerySet

from inventory.models import InventoryItem, StockMovement


def filter_items(*, q: str = "", low_only: bool = False, include_inactive=False):
    qs = InventoryItem.objects.all()
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if q:
        qs = qs.filter(name__icontains=q)
    if low_only:
        qs = qs.filter(quantity__lte=F("reorder_level"))
    return qs.order_by("name")


def low_stock_items() -> QuerySet[InventoryItem]:
    return InventoryItem.objects.filter(is_active=True, quantity__lte=F("reorder_level")).order_by(
        "name"
    )


def active_items() -> QuerySet[InventoryItem]:
    return InventoryItem.objects.filter(is_active=True).order_by("name")


def movements_for(item: InventoryItem) -> QuerySet[StockMovement]:
    return item.movements.select_related("created_by").order_by("-created_at", "-id")


def recent_movements(limit: int = 50) -> QuerySet[StockMovement]:
    return StockMovement.objects.select_related("item", "created_by").order_by(
        "-created_at", "-id"
    )[:limit]


def quantities(item_ids) -> dict[int, tuple]:
    """{item_id: (name, quantity, unit)} for availability checks by other modules."""
    return {
        i.pk: (i.name, i.quantity, i.unit) for i in InventoryItem.objects.filter(pk__in=item_ids)
    }
