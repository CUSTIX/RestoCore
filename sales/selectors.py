import datetime as dt
from decimal import Decimal

from django.db.models import Count, Prefetch, QuerySet, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from inventory import selectors as inventory_selectors
from sales.models import MenuCategory, MenuItem, Order, OrderLine


def public_menu() -> list[MenuCategory]:
    """Categories with their available items, for the public menu page."""
    available = MenuItem.objects.filter(is_available=True).order_by("name")
    cats = MenuCategory.objects.prefetch_related(
        Prefetch("items", queryset=available, to_attr="shown")
    )
    return [c for c in cats if c.shown]


def all_menu_items() -> QuerySet[MenuItem]:
    return MenuItem.objects.select_related("category").order_by("category__sort_order", "name")


def pos_menu() -> list[dict]:
    """Available items with how many portions current stock can make (None = not tracked)."""
    items = list(
        MenuItem.objects.filter(is_available=True)
        .select_related("category")
        .prefetch_related("recipe")
        .order_by("category__sort_order", "name")
    )
    ingredient_ids = {r.inventory_item_id for item in items for r in item.recipe.all()}
    stock = inventory_selectors.quantities(ingredient_ids)
    result = []
    for item in items:
        portions = None
        for r in item.recipe.all():
            on_hand = stock.get(r.inventory_item_id, ("", Decimal("0"), ""))[1]
            can_make = int(on_hand // r.quantity)
            portions = can_make if portions is None else min(portions, can_make)
        result.append({"item": item, "portions": portions})
    return result


def filter_orders(*, date=None, status: str = "") -> QuerySet[Order]:
    qs = Order.objects.select_related("cashier").annotate(item_count=Sum("lines__quantity"))
    if date:
        qs = qs.filter(created_at__date=date)
    if status:
        qs = qs.filter(status=status)
    return qs.order_by("-created_at", "-id")


def order_with_lines(pk: int) -> Order:
    return Order.objects.select_related("cashier", "voided_by").prefetch_related("lines").get(pk=pk)


def kitchen_queue() -> QuerySet[Order]:
    return (
        Order.objects.filter(
            status=Order.Status.PAID,
            kitchen_status__in=(
                Order.KitchenStatus.QUEUED,
                Order.KitchenStatus.PREPARING,
                Order.KitchenStatus.READY,
            ),
        )
        .prefetch_related("lines")
        .order_by("created_at", "id")
    )


def sales_summary(day: dt.date | None = None) -> dict:
    day = day or timezone.localdate()
    paid = Order.objects.filter(status=Order.Status.PAID, created_at__date=day)
    agg = paid.aggregate(revenue=Sum("total"), orders=Count("id"))
    top = (
        OrderLine.objects.filter(order__in=paid)
        .values("name")
        .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-qty", "name")[:5]
    )
    return {
        "day": day,
        "revenue": agg["revenue"] or Decimal("0"),
        "orders": agg["orders"],
        "average": (agg["revenue"] / agg["orders"]) if agg["orders"] else Decimal("0"),
        "top_items": list(top),
        "voided": Order.objects.filter(status=Order.Status.VOIDED, created_at__date=day).count(),
    }


def daily_revenue(days: int = 7) -> list[dict]:
    start = timezone.localdate() - dt.timedelta(days=days - 1)
    rows = (
        Order.objects.filter(status=Order.Status.PAID, created_at__date__gte=start)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("day")
    )
    by_day = {r["day"]: r for r in rows}
    return [
        {
            "day": start + dt.timedelta(days=i),
            "revenue": by_day.get(start + dt.timedelta(days=i), {}).get("revenue") or Decimal("0"),
            "orders": by_day.get(start + dt.timedelta(days=i), {}).get("orders") or 0,
        }
        for i in range(days)
    ]
