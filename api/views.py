"""Read-only JSON API used by the MCP server.

Auth: `Authorization: Bearer <RESTOCORE_API_TOKEN>`. If the token setting is empty the API is off.
Only GET is allowed, and every endpoint reads through the owning module's selectors.
"""

import datetime as dt
import hmac
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from bookings import selectors as bookings
from inventory import selectors as inventory
from sales import selectors as sales
from staff import services as staff_services


def _error(message: str, status: int) -> JsonResponse:
    return JsonResponse({"error": message}, status=status)


def token_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        expected = settings.API_TOKEN
        if not expected:
            return _error("API is disabled. Set RESTOCORE_API_TOKEN to enable it.", 503)
        header = request.headers.get("Authorization", "")
        supplied = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
        if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
            return _error("Invalid or missing API token.", 401)
        return view(request, *args, **kwargs)

    return wrapper


def _date_param(request) -> dt.date:
    raw = request.GET.get("date")
    if not raw:
        return timezone.localdate()
    return dt.date.fromisoformat(raw)  # ValueError handled by caller


@require_GET
@token_required
def bookings_view(request):
    try:
        day = _date_param(request)
    except ValueError:
        return _error("date must be YYYY-MM-DD.", 400)
    rows = bookings.filter_bookings(date=day)
    return JsonResponse(
        {
            "date": day.isoformat(),
            "bookings": [
                {
                    "reference": b.reference,
                    "time": b.time.strftime("%H:%M"),
                    "name": b.name,
                    "party_size": b.party_size,
                    "status": b.status,
                }
                for b in rows
            ],
        }
    )


@require_GET
@token_required
def low_stock_view(request):
    return JsonResponse(
        {
            "items": [
                {
                    "name": i.name,
                    "quantity": str(i.quantity),
                    "unit": i.unit,
                    "reorder_level": str(i.reorder_level),
                }
                for i in inventory.low_stock_items()
            ],
        }
    )


@require_GET
@token_required
def sales_summary_view(request):
    try:
        day = _date_param(request)
    except ValueError:
        return _error("date must be YYYY-MM-DD.", 400)
    s = sales.sales_summary(day)
    return JsonResponse(
        {
            "date": day.isoformat(),
            "revenue": str(s["revenue"]),
            "orders": s["orders"],
            "average_order": str(round(s["average"], 2)),
            "voided": s["voided"],
            "top_items": [
                {"name": t["name"], "quantity": t["qty"], "revenue": str(t["revenue"])}
                for t in s["top_items"]
            ],
        }
    )


@require_GET
@token_required
def menu_view(request):
    return JsonResponse(
        {
            "categories": [
                {
                    "name": c.name,
                    "items": [
                        {"name": i.name, "price": str(i.price), "description": i.description}
                        for i in c.shown
                    ],
                }
                for c in sales.public_menu()
            ],
        }
    )


@require_GET
@token_required
def on_shift_view(request):
    return JsonResponse(
        {
            "on_shift": [
                {
                    "name": str(e.employee),
                    "position": e.employee.position,
                    "since": timezone.localtime(e.clock_in).isoformat(),
                }
                for e in staff_services.on_shift_now()  # not forgotten clock-ins
            ],
        }
    )
