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


def signature_dishes(limit: int = 8) -> list[MenuItem]:
    """Signature dishes first, topped up with other available dishes so it never looks bare."""
    available = MenuItem.objects.filter(is_available=True).select_related("category")
    picks = list(
        available.filter(is_signature=True).order_by("category__sort_order", "name")[:limit]
    )
    if len(picks) < limit:
        picks += list(
            available.exclude(pk__in=[p.pk for p in picks]).order_by("?")[: limit - len(picks)]
        )
    return picks


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
        # Per-portion recipe, so the POS can add up a whole order (dishes share ingredients).
        recipe = {str(r.inventory_item_id): str(r.quantity) for r in item.recipe.all()}
        result.append({"item": item, "portions": portions, "recipe": recipe})
    return result


def pos_ingredient_stock(menu: list[dict]) -> dict[str, dict]:
    """On-hand stock of every ingredient the POS menu uses: {id: {name, qty, unit}}."""
    ids = {int(i) for row in menu for i in row["recipe"]}
    return {
        str(pk): {"name": name, "qty": str(qty), "unit": unit}
        for pk, (name, qty, unit) in inventory_selectors.quantities(ids).items()
    }


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


def sales_between(start: dt.date, end: dt.date) -> dict:
    """Sales report for a date range (inclusive, local dates): totals, per day, per payment
    method, order type, hour and cashier, and the best-selling dishes."""
    in_range = Order.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    paid = in_range.filter(status=Order.Status.PAID)
    agg = paid.aggregate(revenue=Sum("total"), tax=Sum("tax"), orders=Count("id"))
    revenue, orders = agg["revenue"] or Decimal("0"), agg["orders"]
    voided = in_range.filter(status=Order.Status.VOIDED).aggregate(
        n=Count("id"), value=Sum("total")
    )

    def grouped(field):
        return [
            {field: r[field], "revenue": r["revenue"], "orders": r["orders"]}
            for r in paid.values(field)
            .annotate(revenue=Sum("total"), orders=Count("id"))
            .order_by("-revenue")
        ]

    by_day = (
        paid.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("day")
    )
    by_hour: dict[int, dict] = {}
    for created_at, total in paid.values_list("created_at", "total"):
        hour = timezone.localtime(created_at).hour
        row = by_hour.setdefault(
            hour, {"hour": f"{hour:02d}:00", "revenue": Decimal("0"), "orders": 0}
        )
        row["revenue"] += total
        row["orders"] += 1
    by_cashier = (
        paid.values("cashier__first_name", "cashier__last_name", "cashier__username")
        .annotate(revenue=Sum("total"), orders=Count("id"))
        .order_by("-revenue")
    )
    top = (
        OrderLine.objects.filter(order__in=paid)
        .values("name")
        .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue", "name")
    )
    return {
        "start": start,
        "end": end,
        "revenue": revenue,
        "tax_collected": agg["tax"] or Decimal("0"),
        "orders": orders,
        "average_order": (revenue / orders).quantize(Decimal("0.01")) if orders else Decimal("0"),
        "voided_orders": voided["n"],
        "voided_value": voided["value"] or Decimal("0"),
        "by_day": list(by_day),
        "by_payment_method": grouped("payment_method"),
        "by_order_type": grouped("order_type"),
        "by_hour": [by_hour[h] for h in sorted(by_hour)],
        "by_cashier": [
            {
                "cashier": f"{r['cashier__first_name']} {r['cashier__last_name']}".strip()
                or r["cashier__username"],
                "revenue": r["revenue"],
                "orders": r["orders"],
            }
            for r in by_cashier
        ],
        "items": list(top),
    }


def recent_orders(*, date=None, status: str = "", limit: int = 30) -> list[Order]:
    """Orders with their lines, newest first (for summaries and the assistant)."""
    return list(filter_orders(date=date, status=status).prefetch_related("lines")[:limit])
