from decimal import Decimal

from django.db.models import Count, F, Q, QuerySet, Sum

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


def recipe_choices(*, keep_id: int | None = None) -> QuerySet[InventoryItem]:
    """Ingredients a recipe line may use: active ones, plus the one it already uses (if any)."""
    return InventoryItem.objects.filter(Q(is_active=True) | Q(pk=keep_id)).order_by("name")


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


def movement_totals(start, end) -> list[dict]:
    """Stock change per item and reason between two local dates, with its cost at today's
    cost per unit (e.g. how much waste cost this month)."""
    rows = (
        StockMovement.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
        .values("item__name", "item__unit", "item__cost_per_unit", "reason")
        .annotate(change=Sum("change"), movements=Count("id"))
        .order_by("item__name", "reason")
    )
    return [
        {
            "item": r["item__name"],
            "unit": r["item__unit"],
            "reason": r["reason"],
            "change": r["change"],
            "movements": r["movements"],
            "cost": (abs(r["change"]) * r["item__cost_per_unit"]).quantize(Decimal("0.01")),
        }
        for r in rows
    ]
