"""Read-only tools the assistant may call. Each one reads through the owning module's selectors
(never another app's models), validates its arguments, and caps how much it returns.

Customer phone numbers and emails, and staff phone numbers, are never handed to the model:
the owner can see them in the app, and they aren't needed to answer business questions.
"""

import datetime as dt
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from bookings import selectors as bookings
from inventory import selectors as inventory
from payroll import selectors as payroll
from sales import selectors as sales
from staff import selectors as staff
from staff import services as staff_services

MAX_RANGE_DAYS = 366
MAX_ROWS = 60


class ToolError(ValueError):
    """Bad arguments from the model. Sent back to it so it can correct itself."""


@dataclass(frozen=True)
class Tool:
    name: str
    label: str  # shown to the owner under the answer ("Looked at: ...")
    description: str
    parameters: dict
    run: Callable[..., dict]

    def declaration(self) -> dict:
        decl = {"name": self.name, "description": self.description}
        if self.parameters:
            decl["parameters"] = {"type": "object", "properties": self.parameters}
        return decl


TOOLS: dict[str, Tool] = {}


def tool(name: str, label: str, description: str, **parameters):
    def register(fn):
        TOOLS[name] = Tool(name, label, description, parameters, fn)
        return fn

    return register


# ---- argument helpers ------------------------------------------------------------------------

DATE = {"type": "string", "description": "Date as YYYY-MM-DD."}


def _date(value, *, default: dt.date | None = None) -> dt.date:
    if value in (None, ""):
        if default is None:
            raise ToolError("A date (YYYY-MM-DD) is required.")
        return default
    try:
        return dt.date.fromisoformat(str(value))
    except ValueError as exc:
        raise ToolError(f"'{value}' is not a date; use YYYY-MM-DD.") from exc


def _range(start, end, *, max_days: int = MAX_RANGE_DAYS) -> tuple[dt.date, dt.date]:
    today = timezone.localdate()
    first, last = _date(start, default=today), _date(end, default=today)
    if last < first:
        raise ToolError("end_date is before start_date.")
    if (last - first).days >= max_days:
        raise ToolError(f"Ask for at most {max_days} days at a time.")
    return first, last


def _choice(value, allowed, name: str) -> str:
    value = (value or "").strip().lower()
    if value and value not in allowed:
        raise ToolError(f"{name} must be one of: {', '.join(sorted(allowed))}.")
    return value


def _limit(value, default: int = 30) -> int:
    try:
        return max(1, min(int(value or default), MAX_ROWS))
    except (TypeError, ValueError):
        return default


def _name(user) -> str:
    return user.get_full_name() or user.username


def _contains(needle: str, haystack: str) -> bool:
    return not needle or needle.lower() in haystack.lower()


# ---- overview --------------------------------------------------------------------------------


@tool(
    "get_overview",
    "Today at a glance",
    "Snapshot of right now: today's sales, bookings, kitchen queue, who is on shift, forgotten "
    "clock-ins, low-stock items and pending leave requests. Start here for 'how are we doing'.",
)
def get_overview() -> dict:
    today = sales.sales_summary()
    return {
        "date": timezone.localdate(),
        "now": timezone.localtime().strftime("%H:%M"),
        "sales_today": {
            "revenue": today["revenue"],
            "paid_orders": today["orders"],
            "average_order": today["average"],
            "voided_orders": today["voided"],
            "top_items": today["top_items"],
        },
        "bookings_today": bookings.today_summary(),
        "kitchen_queue": sales.kitchen_queue().count(),
        "on_shift_now": [_name(e.employee.user) for e in staff_services.on_shift_now()],
        "forgotten_clock_ins": staff_services.forgotten_clock_in_count(),
        "low_stock": [i.name for i in inventory.low_stock_items()],
        "pending_leave_requests": staff.leave_requests(status="pending").count(),
    }


# ---- sales -----------------------------------------------------------------------------------


@tool(
    "sales_report",
    "Sales report",
    "Sales between two dates (inclusive): revenue, orders, average order, tax, voids, and "
    "breakdowns per day, payment method, order type, hour of day, cashier and dish (revenue and "
    "quantity per dish, best first). Use it for any revenue, trend or best-seller question; call "
    "it twice to compare periods.",
    start_date=DATE,
    end_date=DATE,
)
def sales_report(start_date=None, end_date=None) -> dict:
    report = sales.sales_between(*_range(start_date, end_date))
    report["items"] = report["items"][:40]
    return report


@tool(
    "list_orders",
    "Orders",
    "Individual orders on one day (newest first) with their dishes, totals, payment, table, "
    "status and kitchen status. Status: paid or voided.",
    date=DATE,
    status={"type": "string", "description": "paid or voided (optional)."},
    limit={"type": "integer", "description": "Max orders to return (1-60)."},
)
def list_orders(date=None, status=None, limit=None) -> dict:
    day = _date(date, default=timezone.localdate())
    status = _choice(status, {"paid", "voided"}, "status")
    orders = sales.recent_orders(date=day, status=status, limit=_limit(limit))
    return {
        "date": day,
        "orders": [
            {
                "number": o.number,
                "time": timezone.localtime(o.created_at).strftime("%H:%M"),
                "type": o.order_type,
                "table": o.table_label,
                "payment": o.payment_method,
                "total": o.total,
                "status": o.status,
                "kitchen_status": o.kitchen_status,
                "cashier": _name(o.cashier),
                "void_reason": o.void_reason,
                "items": [f"{line.quantity}x {line.name}" for line in o.lines.all()],
            }
            for o in orders
        ],
    }


@tool(
    "get_menu",
    "Menu",
    "Every menu item with category, price, whether it's available or a signature dish, and how "
    "many portions current stock can make (null = stock not tracked for it).",
)
def get_menu() -> dict:
    portions = {row["item"].pk: row["portions"] for row in sales.pos_menu()}
    return {
        "items": [
            {
                "name": item.name,
                "category": item.category.name,
                "price": item.price,
                "available": item.is_available,
                "signature": item.is_signature,
                "portions_in_stock": portions.get(item.pk),
            }
            for item in sales.all_menu_items()
        ]
    }


# ---- bookings --------------------------------------------------------------------------------

BOOKING_STATUSES = {"pending", "confirmed", "seated", "completed", "cancelled", "no_show"}


@tool(
    "list_bookings",
    "Bookings",
    "Table bookings. Give a date for that whole day; otherwise 'when' picks upcoming (default) "
    "or past. Optional status and a name/reference search. Contact details are not included.",
    date=DATE,
    when={"type": "string", "description": "upcoming or past (ignored when date is given)."},
    status={"type": "string", "description": ", ".join(sorted(BOOKING_STATUSES))},
    search={"type": "string", "description": "Guest name or booking reference."},
    limit={"type": "integer", "description": "Max bookings to return (1-60)."},
)
def list_bookings(date=None, when=None, status=None, search=None, limit=None) -> dict:
    day = _date(date) if date else None
    when = _choice(when, {"upcoming", "past"}, "when") or "upcoming"
    status = _choice(status, BOOKING_STATUSES, "status")
    rows = bookings.filter_bookings(date=day, status=status, q=(search or "")[:60], when=when)
    return {
        "bookings": [
            {
                "reference": b.reference,
                "date": b.date,
                "time": b.time.strftime("%H:%M"),
                "guest": b.name,
                "party_size": b.party_size,
                "status": b.status,
                "source": b.source,
                "notes": b.notes,
            }
            for b in rows[: _limit(limit)]
        ]
    }


@tool(
    "booking_stats",
    "Booking stats",
    "Booking totals between two dates: count per status and source, guests expected or served, "
    "and the no-show rate (no-shows / (seated + completed + no-shows)).",
    start_date=DATE,
    end_date=DATE,
)
def booking_stats(start_date=None, end_date=None) -> dict:
    return bookings.stats_between(*_range(start_date, end_date))


# ---- inventory -------------------------------------------------------------------------------


@tool(
    "get_inventory",
    "Inventory",
    "Ingredients on hand: quantity, unit, reorder level, cost per unit, stock value and whether "
    "it's low. 'shortfall' is how far below the reorder level it is, with what that costs to "
    "top up. Totals are included.",
    low_only={"type": "boolean", "description": "Only items at or below their reorder level."},
    search={"type": "string", "description": "Part of an ingredient name."},
)
def get_inventory(low_only=False, search=None) -> dict:
    items = inventory.filter_items(q=(search or "")[:60], low_only=bool(low_only))
    rows, value, top_up = [], Decimal("0"), Decimal("0")
    for i in items:
        shortfall = max(i.reorder_level - i.quantity, Decimal("0"))
        row_value = (i.quantity * i.cost_per_unit).quantize(Decimal("0.01"))
        row_top_up = (shortfall * i.cost_per_unit).quantize(Decimal("0.01"))
        value, top_up = value + row_value, top_up + row_top_up
        rows.append(
            {
                "name": i.name,
                "quantity": i.quantity,
                "unit": i.unit,
                "reorder_level": i.reorder_level,
                "cost_per_unit": i.cost_per_unit,
                "stock_value": row_value,
                "low": i.quantity <= i.reorder_level,
                "shortfall": shortfall,
                "cost_to_reach_reorder_level": row_top_up,
            }
        )
    return {"items": rows, "total_stock_value": value, "total_cost_to_reach_reorder_levels": top_up}


@tool(
    "stock_movements",
    "Stock movements",
    "How stock changed between two dates, per ingredient and reason (purchase, sale, sale_void, "
    "waste, count), with the cost of each at today's cost per unit. Use for waste, usage and "
    "purchasing questions.",
    start_date=DATE,
    end_date=DATE,
    reason={"type": "string", "description": "purchase, sale, sale_void, waste or count."},
)
def stock_movements(start_date=None, end_date=None, reason=None) -> dict:
    first, last = _range(start_date, end_date)
    reason = _choice(reason, {"purchase", "sale", "sale_void", "waste", "count"}, "reason")
    rows = [
        r for r in inventory.movement_totals(first, last) if not reason or r["reason"] == reason
    ]
    return {
        "start": first,
        "end": last,
        "rows": rows[:150],
        "total_cost": sum((r["cost"] for r in rows), Decimal("0")),
    }


# ---- staff -----------------------------------------------------------------------------------


@tool(
    "list_employees",
    "Employees",
    "Staff list: name, role, position, hourly rate, hire date and whether they're active.",
    include_inactive={"type": "boolean", "description": "Also list people who have left."},
)
def list_employees(include_inactive=False) -> dict:
    return {
        "employees": [
            {
                "name": _name(e.user),
                "role": staff_services.primary_role(e.user),
                "position": e.position,
                "hourly_rate": e.hourly_rate,
                "hire_date": e.hire_date,
                "active": e.is_active,
            }
            for e in staff.filter_employees(include_inactive=bool(include_inactive))
        ]
    }


@tool(
    "get_schedule",
    "Schedule",
    "Planned shifts between two dates (at most 31 days), optionally for one person (name search).",
    start_date=DATE,
    end_date=DATE,
    employee={"type": "string", "description": "Part of the employee's name (optional)."},
)
def get_schedule(start_date=None, end_date=None, employee=None) -> dict:
    first, last = _range(start_date, end_date, max_days=31)
    shifts = [
        {
            "date": s.date,
            "employee": _name(s.employee.user),
            "start": s.start_time.strftime("%H:%M"),
            "end": s.end_time.strftime("%H:%M"),
            "hours": s.hours,
            "note": s.note,
        }
        for s in staff.shifts_between(first, last)
        if _contains(employee or "", _name(s.employee.user))
    ]
    return {"start": first, "end": last, "shifts": shifts[:200], "total_shifts": len(shifts)}


@tool(
    "get_attendance",
    "Attendance",
    "Hours actually worked (clocked in and out) per person between two dates, who is clocked in "
    "right now, and clock-ins that were never closed (not paid until a manager closes them).",
    start_date=DATE,
    end_date=DATE,
)
def get_attendance(start_date=None, end_date=None) -> dict:
    first, last = _range(start_date, end_date)
    hours = staff.hours_worked(first, last)
    people = {e.pk: _name(e.user) for e in staff.employees_by_ids(hours)}
    return {
        "start": first,
        "end": last,
        "hours_worked": sorted(
            ({"employee": people.get(pk, f"#{pk}"), "hours": h} for pk, h in hours.items()),
            key=lambda r: -r["hours"],
        ),
        "clocked_in_now": [
            {
                "employee": _name(e.employee.user),
                "since": timezone.localtime(e.clock_in).strftime("%Y-%m-%d %H:%M"),
            }
            for e in staff_services.on_shift_now()
        ],
        "never_closed": [
            {
                "employee": _name(e.employee.user),
                "clock_in": timezone.localtime(e.clock_in).strftime("%Y-%m-%d %H:%M"),
            }
            for e in staff.open_entries_between(first, last)
        ],
    }


@tool(
    "list_leave",
    "Leave requests",
    "Leave requests (newest first), optionally by status and person: type, dates, days, reason, "
    "and who reviewed it.",
    status={"type": "string", "description": "pending, approved, rejected or cancelled."},
    employee={"type": "string", "description": "Part of the employee's name (optional)."},
)
def list_leave(status=None, employee=None) -> dict:
    status = _choice(status, {"pending", "approved", "rejected", "cancelled"}, "status")
    rows = [
        {
            "employee": _name(r.employee.user),
            "type": r.leave_type,
            "start": r.start_date,
            "end": r.end_date,
            "days": r.days,
            "status": r.status,
            "reason": r.reason,
            "reviewed_by": _name(r.reviewed_by) if r.reviewed_by else None,
            "review_note": r.review_note,
        }
        for r in staff.leave_requests(status=status)
        if _contains(employee or "", _name(r.employee.user))
    ]
    return {"leave_requests": rows[:MAX_ROWS]}


# ---- payroll ---------------------------------------------------------------------------------


@tool(
    "list_pay_periods",
    "Pay periods",
    "Payroll periods (newest first) with status (draft/finalized), number of payslips and "
    "total gross and net pay. Payroll uses demo rates.",
)
def list_pay_periods() -> dict:
    return {
        "periods": [
            {
                "id": p.pk,
                "start": p.start_date,
                "end": p.end_date,
                "status": p.status,
                "payslips": p.slip_count,
                "total_gross": p.total_gross or Decimal("0"),
                "total_net": p.total_net or Decimal("0"),
            }
            for p in payroll.periods()[:24]
        ]
    }


@tool(
    "get_pay_period",
    "Payroll period",
    "One payroll period's totals and every payslip (hours, paid leave days, gross, deductions, "
    "net). Get the id from list_pay_periods.",
    period_id={"type": "integer", "description": "Id from list_pay_periods."},
)
def get_pay_period(period_id=None) -> dict:
    try:
        period = payroll.periods().filter(pk=int(period_id)).first()
    except (TypeError, ValueError) as exc:
        raise ToolError("period_id must be a number from list_pay_periods.") from exc
    if period is None:
        raise ToolError("No pay period with that id.")
    return {
        "id": period.pk,
        "start": period.start_date,
        "end": period.end_date,
        "status": period.status,
        "totals": payroll.period_totals(period),
        "payslips": [
            {
                "employee": s.employee_name,
                "position": s.position,
                "hours": s.hours_worked,
                "paid_leave_days": s.paid_leave_days,
                "gross": s.gross_pay,
                "deductions": s.total_deductions,
                "net": s.net_pay,
            }
            for s in payroll.payslips_for(period)
        ],
        "deduction_rates": [
            {"name": r.name, "rate": r.rate, "active": r.is_active}
            for r in payroll.deduction_rates()
        ],
    }


def declarations() -> list[dict]:
    return [t.declaration() for t in TOOLS.values()]


def run(name: str, args: dict | None) -> dict:
    """Call a tool by name. Unknown tools and bad arguments come back as {"error": ...}."""
    found = TOOLS.get(name)
    if not found:
        return {"error": f"There is no tool called {name}."}
    args = {k: v for k, v in (args or {}).items() if k in found.parameters}
    try:
        return found.run(**args)
    except ToolError as exc:
        return {"error": str(exc)}
