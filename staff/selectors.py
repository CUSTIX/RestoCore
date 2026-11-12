import datetime as dt
from decimal import Decimal

from django.db.models import Q, QuerySet
from django.utils import timezone

from staff.models import Employee, LeaveRequest, Shift, TimeEntry


def employee_for_user(user) -> Employee | None:
    if not user.is_authenticated:
        return None
    return Employee.objects.filter(user=user).select_related("user").first()


def filter_employees(*, q: str = "", include_inactive: bool = False) -> QuerySet[Employee]:
    qs = Employee.objects.select_related("user").prefetch_related("user__groups")
    if not include_inactive:
        qs = qs.filter(is_active=True)
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q)
            | Q(user__last_name__icontains=q)
            | Q(user__username__icontains=q)
            | Q(position__icontains=q)
        )
    return qs


def active_employees() -> QuerySet[Employee]:
    return Employee.objects.filter(is_active=True).select_related("user")


def shifts_between(start: dt.date, end: dt.date, employee=None) -> QuerySet[Shift]:
    qs = Shift.objects.filter(date__gte=start, date__lte=end).select_related("employee__user")
    if employee:
        qs = qs.filter(employee=employee)
    return qs.order_by("date", "start_time", "id")


def scheduled_end(employee_id: int, date: dt.date) -> dt.time | None:
    """When the person's last shift on `date` was planned to end (None if not scheduled)."""
    return (
        Shift.objects.filter(employee_id=employee_id, date=date)
        .order_by("-end_time")
        .values_list("end_time", flat=True)
        .first()
    )


def upcoming_shifts(employee: Employee, days: int = 14) -> QuerySet[Shift]:
    today = timezone.localdate()
    return shifts_between(today, today + dt.timedelta(days=days), employee=employee)


def open_entry(employee: Employee) -> TimeEntry | None:
    return TimeEntry.objects.filter(employee=employee, clock_out__isnull=True).first()


def time_entries(*, date=None, employee=None) -> QuerySet[TimeEntry]:
    qs = TimeEntry.objects.select_related("employee__user")
    if date:
        qs = qs.filter(clock_in__date=date)
    if employee:
        qs = qs.filter(employee=employee)
    return qs.order_by("-clock_in", "-id")


def clocked_in_now() -> QuerySet[TimeEntry]:
    return TimeEntry.objects.filter(clock_out__isnull=True).select_related("employee__user")


def leave_requests(*, status: str = "", employee=None) -> QuerySet[LeaveRequest]:
    qs = LeaveRequest.objects.select_related("employee__user", "reviewed_by").prefetch_related(
        "employee__user__groups"  # role checks per row without extra queries
    )
    if status:
        qs = qs.filter(status=status)
    if employee:
        qs = qs.filter(employee=employee)
    return qs.order_by("-created_at", "-id")


def hours_worked(start: dt.date, end: dt.date) -> dict[int, Decimal]:
    """Closed attendance hours per employee id, for clock-ins between start and end (local)."""
    totals: dict[int, Decimal] = {}
    entries = TimeEntry.objects.filter(
        clock_in__date__gte=start, clock_in__date__lte=end, clock_out__isnull=False
    )
    for entry in entries:
        totals[entry.employee_id] = totals.get(entry.employee_id, Decimal("0")) + entry.hours
    return totals


def approved_leave_days(start: dt.date, end: dt.date) -> dict[int, int]:
    """Paid leave days inside the period per employee id (unpaid leave excluded).

    A day the employee actually worked (clocked in) is paid as worked hours, not also as a
    leave day: otherwise coming in during approved leave would be paid twice.
    """
    worked_days: dict[int, set[dt.date]] = {}
    for employee_id, clock_in in TimeEntry.objects.filter(
        clock_in__date__gte=start, clock_in__date__lte=end
    ).values_list("employee_id", "clock_in"):
        worked_days.setdefault(employee_id, set()).add(timezone.localtime(clock_in).date())
    days: dict[int, int] = {}
    for leave in LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=end,
        end_date__gte=start,
    ).exclude(leave_type=LeaveRequest.LeaveType.UNPAID):
        first, last = max(leave.start_date, start), min(leave.end_date, end)
        dates = {first + dt.timedelta(days=i) for i in range((last - first).days + 1)}
        paid = len(dates - worked_days.get(leave.employee_id, set()))
        if paid:
            days[leave.employee_id] = days.get(leave.employee_id, 0) + paid
    return days


def open_entries_between(start: dt.date, end: dt.date) -> QuerySet[TimeEntry]:
    """Clock-ins in the period that were never clocked out: not paid until a manager closes them."""
    return (
        TimeEntry.objects.filter(
            clock_in__date__gte=start, clock_in__date__lte=end, clock_out__isnull=True
        )
        .select_related("employee__user")
        .order_by("clock_in")
    )


def employees_by_ids(ids) -> QuerySet[Employee]:
    """Any employee, active or not (payroll pays people who left mid-period too)."""
    return Employee.objects.filter(pk__in=ids).select_related("user").order_by("pk")
