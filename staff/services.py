"""Staff rules: who may manage whom, shift overlaps, clocking and leave approval."""

import datetime as dt

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts import services as account_services
from core.roles import MANAGER, OWNER, has_role, user_roles
from staff.models import Employee, LeaveRequest, Shift, TimeEntry

PRIVILEGED_ROLES = (OWNER, MANAGER)
MAX_SHIFT_HOURS = 16  # longer than this, a clock-in was almost certainly forgotten


def primary_role(user) -> str:
    roles = user_roles(user)
    for role in (OWNER, MANAGER, "Cashier", "Kitchen", "Staff"):
        if role in roles:
            return role
    return ""


def assert_can_manage(actor, *, target_role: str, target_user=None) -> None:
    """Only an Owner may create, edit or assign Owner and Manager accounts."""
    if (
        settings.DEMO_MODE
        and target_user is not None
        and target_user.username in settings.DEMO_ACCOUNTS
    ):
        raise PermissionDenied("The shared demo accounts can't be changed in the public demo.")
    if has_role(actor, OWNER):
        return
    if not has_role(actor, MANAGER):
        raise PermissionDenied("Only managers and owners can manage employees.")
    if target_role in PRIVILEGED_ROLES:
        raise PermissionDenied("Only an owner can assign the Owner or Manager role.")
    if target_user is not None and has_role(target_user, *PRIVILEGED_ROLES):
        raise PermissionDenied("Only an owner can edit an owner or manager.")


def can_edit_employee(actor, target_user) -> bool:
    """For templates: should `actor` see an Edit link for this person?"""
    try:
        assert_can_manage(actor, target_role=primary_role(target_user), target_user=target_user)
    except PermissionDenied:
        return False
    return True


# ---- Employees ----------------------------------------------------------------------------


@transaction.atomic
def create_employee(
    *,
    actor,
    username,
    password,
    first_name,
    last_name,
    email,
    role,
    position,
    phone,
    hourly_rate,
    hire_date,
) -> Employee:
    assert_can_manage(actor, target_role=role)
    try:
        with transaction.atomic():
            user = account_services.create_user_with_role(
                username=username,
                password=password,
                role=role,
                first_name=first_name,
                last_name=last_name,
                email=email,
            )
    except IntegrityError as exc:
        raise ValidationError("That username is already taken.") from exc
    return Employee.objects.create(
        user=user, position=position, phone=phone, hourly_rate=hourly_rate, hire_date=hire_date
    )


@transaction.atomic
def update_employee(
    employee: Employee,
    *,
    actor,
    role,
    first_name,
    last_name,
    email,
    position,
    phone,
    hourly_rate,
    hire_date,
    is_active,
) -> Employee:
    assert_can_manage(actor, target_role=role, target_user=employee.user)
    if employee.user_id == actor.pk and not is_active:
        raise ValidationError("You cannot deactivate your own account.")
    if employee.user_id == actor.pk and role != primary_role(actor):
        raise ValidationError("You cannot change your own role.")
    leaving = employee.is_active and not is_active
    user = employee.user
    user.first_name, user.last_name, user.email = first_name, last_name, email
    user.is_active = is_active  # deactivated employees can no longer log in
    user.save(update_fields=["first_name", "last_name", "email", "is_active"])
    account_services.set_user_role(user, role)
    employee.position, employee.phone = position, phone
    employee.hourly_rate, employee.hire_date, employee.is_active = hourly_rate, hire_date, is_active
    employee.save()
    employee.cleanup = _offboard(employee) if leaving else {}
    return employee


def _offboard(employee: Employee) -> dict[str, int]:
    """Someone who left shouldn't stay on the schedule or in the leave queue.
    (Hours already worked stay and are still paid: see payroll.)"""
    shifts = Shift.objects.filter(employee=employee, date__gte=timezone.localdate()).delete()[0]
    leave = LeaveRequest.objects.filter(
        employee=employee, status=LeaveRequest.Status.PENDING
    ).update(status=LeaveRequest.Status.CANCELLED)
    return {"shifts": shifts, "leave": leave}


# ---- Shifts -------------------------------------------------------------------------------


def _check_shift(employee: Employee, date, start, end, exclude_id=None) -> None:
    if end <= start:
        raise ValidationError("The shift must end after it starts.")
    overlapping = Shift.objects.filter(
        employee=employee, date=date, start_time__lt=end, end_time__gt=start
    )
    if exclude_id:
        overlapping = overlapping.exclude(pk=exclude_id)
    if overlapping.exists():
        raise ValidationError(f"{employee} already has a shift that overlaps this time.")
    on_leave = LeaveRequest.objects.filter(
        employee=employee,
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=date,
        end_date__gte=date,
    ).exists()
    if on_leave:
        raise ValidationError(f"{employee} is on approved leave that day.")


@transaction.atomic
def save_shift(
    *, shift: Shift | None = None, employee, date, start_time, end_time, note=""
) -> Shift:
    if not employee.is_active:
        raise ValidationError("Inactive employees cannot be scheduled.")
    today = timezone.localdate()
    if date < today and (shift is None or shift.date != date):
        # The schedule plans work ahead. A day that is over is recorded by attendance, not
        # rewritten as a shift (an existing past shift can still be edited in place).
        raise ValidationError("You can't schedule a shift on a day that has already passed.")
    _check_shift(employee, date, start_time, end_time, exclude_id=shift.pk if shift else None)
    shift = shift or Shift()
    shift.employee, shift.date = employee, date
    shift.start_time, shift.end_time, shift.note = start_time, end_time, note
    shift.save()
    return shift


def delete_shift(shift: Shift) -> None:
    shift.delete()


# ---- Attendance ---------------------------------------------------------------------------


@transaction.atomic
def clock_in(employee: Employee, *, at: dt.datetime | None = None) -> TimeEntry:
    if not employee.is_active:
        raise ValidationError("Inactive employees cannot clock in.")
    Employee.objects.select_for_update().get(pk=employee.pk)  # serialise clicks per employee
    current = TimeEntry.objects.filter(employee=employee, clock_out__isnull=True).first()
    if current is not None:
        if timezone.now() - current.clock_in > dt.timedelta(hours=MAX_SHIFT_HOURS):
            raise ValidationError(
                f"You're still clocked in from {_since(current)}. "
                "Ask a manager to close that entry first."
            )
        raise ValidationError("You are already clocked in.")
    return TimeEntry.objects.create(employee=employee, clock_in=at or timezone.now())


def _since(entry: TimeEntry) -> str:
    local = timezone.localtime(entry.clock_in)
    return f"{local:%b} {local.day}, {local:%I}".replace(" 0", " ") + f":{local:%M %p}"


@transaction.atomic
def clock_out(employee: Employee, *, at: dt.datetime | None = None) -> TimeEntry:
    entry = (
        TimeEntry.objects.select_for_update()
        .filter(employee=employee, clock_out__isnull=True)
        .first()
    )
    if entry is None:
        raise ValidationError("You are not clocked in.")
    at = at or timezone.now()
    if at <= entry.clock_in:
        raise ValidationError("Clock-out must be after clock-in.")
    if at - entry.clock_in > dt.timedelta(hours=MAX_SHIFT_HOURS):
        # Clocking out now would pay a 20+ hour "shift". A manager sets the real time instead.
        raise ValidationError(
            f"Your clock-in from {_since(entry)} was never closed. "
            "Ask a manager to set the time you actually left; then you can clock in again."
        )
    entry.clock_out = at
    entry.save(update_fields=["clock_out"])
    return entry


def on_shift_now():
    """Open clock-ins that are plausibly still a shift in progress (dashboard "On shift now")."""
    cutoff = timezone.now() - dt.timedelta(hours=MAX_SHIFT_HOURS)
    return TimeEntry.objects.filter(clock_out__isnull=True, clock_in__gte=cutoff).select_related(
        "employee__user"
    )


def forgotten_clock_in_count() -> int:
    cutoff = timezone.now() - dt.timedelta(hours=MAX_SHIFT_HOURS)
    return TimeEntry.objects.filter(clock_out__isnull=True, clock_in__lt=cutoff).count()


def entry_needs_manager(entry: TimeEntry | None) -> bool:
    """Open longer than a plausible shift: only a manager can close it (see clock_out)."""
    return bool(entry) and timezone.now() - entry.clock_in > dt.timedelta(hours=MAX_SHIFT_HOURS)


def reviewable_leave_count(reviewer) -> int:
    """Pending requests this person can actually approve or reject (dashboard tile)."""
    from staff import selectors

    pending = selectors.leave_requests(status=LeaveRequest.Status.PENDING)
    return sum(1 for leave in pending if not review_blocker(leave, reviewer))


@transaction.atomic
def close_entry(entry: TimeEntry, *, at: dt.datetime, by) -> TimeEntry:
    """A manager closes a forgotten clock-in with the time the person actually left."""
    if not has_role(by, *PRIVILEGED_ROLES):
        raise PermissionDenied("Only managers and owners can correct attendance.")
    entry = TimeEntry.objects.select_for_update().get(pk=entry.pk)
    if entry.clock_out is not None:
        raise ValidationError("This entry is already closed.")
    if at <= entry.clock_in:
        raise ValidationError("The clock-out time must be after the clock-in.")
    if at > timezone.now():
        raise ValidationError("The clock-out time can't be in the future.")
    if at - entry.clock_in > dt.timedelta(hours=MAX_SHIFT_HOURS):
        raise ValidationError(f"A shift can't be longer than {MAX_SHIFT_HOURS} hours.")
    entry.clock_out = at
    entry.save(update_fields=["clock_out"])
    return entry


# ---- Leave --------------------------------------------------------------------------------


@transaction.atomic
def request_leave(
    employee: Employee, *, leave_type, start_date, end_date, reason=""
) -> LeaveRequest:
    if end_date < start_date:
        raise ValidationError("The end date cannot be before the start date.")
    if start_date < timezone.localdate():
        raise ValidationError("Leave cannot start in the past.")
    if (end_date - start_date).days >= 60:
        raise ValidationError("A single leave request can cover at most 60 days.")
    overlap = LeaveRequest.objects.filter(
        employee=employee,
        status__in=(LeaveRequest.Status.PENDING, LeaveRequest.Status.APPROVED),
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()
    if overlap:
        raise ValidationError("You already have a pending or approved request for those dates.")
    return LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
    )


def review_blocker(leave: LeaveRequest, reviewer) -> str:
    """Why `reviewer` may not approve/reject this request ("" when they may). One rule for both
    the buttons on the page and the server, so the page never offers what the server refuses."""
    if leave.employee.user_id == reviewer.pk:
        return "Your own request: another manager or the owner reviews it."
    if not has_role(reviewer, *PRIVILEGED_ROLES):
        return "Only managers and owners can review leave."
    if has_role(leave.employee.user, *PRIVILEGED_ROLES) and not has_role(reviewer, OWNER):
        return "A manager's leave is reviewed by the owner."
    return ""


def shifts_during_leave(leave: LeaveRequest):
    """Scheduled shifts (today onwards) that approving this leave would remove."""
    first_day = max(leave.start_date, timezone.localdate())
    return Shift.objects.filter(
        employee_id=leave.employee_id, date__gte=first_day, date__lte=leave.end_date
    )


@transaction.atomic
def review_leave(leave: LeaveRequest, *, reviewer, approve: bool, note="") -> LeaveRequest:
    """Approve or reject. Approving removes the person's upcoming shifts on those days, so the
    schedule never shows someone working while on approved leave (`leave.removed_shifts`)."""
    leave = (
        LeaveRequest.objects.select_for_update().select_related("employee__user").get(pk=leave.pk)
    )
    if leave.status != LeaveRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be reviewed.")
    blocker = review_blocker(leave, reviewer)
    if blocker:
        raise PermissionDenied(blocker)
    leave.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    leave.reviewed_by, leave.reviewed_at, leave.review_note = reviewer, timezone.now(), note
    leave.save()
    leave.removed_shifts = shifts_during_leave(leave).delete()[0] if approve else 0
    return leave


@transaction.atomic
def cancel_leave(leave: LeaveRequest, *, employee: Employee) -> LeaveRequest:
    # Re-read under lock: the caller's copy may be stale (e.g. approved in another tab).
    leave = LeaveRequest.objects.select_for_update().get(pk=leave.pk)
    if leave.employee_id != employee.pk:
        raise PermissionDenied("You can only cancel your own requests.")
    if leave.status != LeaveRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be cancelled.")
    leave.status = LeaveRequest.Status.CANCELLED
    leave.save(update_fields=["status", "updated_at"])
    return leave
