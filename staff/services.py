"""Staff rules: who may manage whom, shift overlaps, clocking and leave approval."""

import datetime as dt

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts import services as account_services
from core.roles import MANAGER, OWNER, has_role, user_roles
from staff.models import Employee, LeaveRequest, Shift, TimeEntry

PRIVILEGED_ROLES = (OWNER, MANAGER)


def primary_role(user) -> str:
    roles = user_roles(user)
    for role in (OWNER, MANAGER, "Cashier", "Kitchen", "Staff"):
        if role in roles:
            return role
    return ""


def assert_can_manage(actor, *, target_role: str, target_user=None) -> None:
    """Only an Owner may create, edit or assign Owner and Manager accounts."""
    if has_role(actor, OWNER):
        return
    if not has_role(actor, MANAGER):
        raise PermissionDenied("Only managers and owners can manage employees.")
    if target_role in PRIVILEGED_ROLES:
        raise PermissionDenied("Only an owner can assign the Owner or Manager role.")
    if target_user is not None and has_role(target_user, *PRIVILEGED_ROLES):
        raise PermissionDenied("Only an owner can edit an owner or manager.")


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
    user = employee.user
    user.first_name, user.last_name, user.email = first_name, last_name, email
    user.is_active = is_active  # deactivated employees can no longer log in
    user.save(update_fields=["first_name", "last_name", "email", "is_active"])
    account_services.set_user_role(user, role)
    employee.position, employee.phone = position, phone
    employee.hourly_rate, employee.hire_date, employee.is_active = hourly_rate, hire_date, is_active
    employee.save()
    return employee


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
    if TimeEntry.objects.filter(employee=employee, clock_out__isnull=True).exists():
        raise ValidationError("You are already clocked in.")
    return TimeEntry.objects.create(employee=employee, clock_in=at or timezone.now())


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


@transaction.atomic
def review_leave(leave: LeaveRequest, *, reviewer, approve: bool, note="") -> LeaveRequest:
    leave = (
        LeaveRequest.objects.select_for_update().select_related("employee__user").get(pk=leave.pk)
    )
    if leave.status != LeaveRequest.Status.PENDING:
        raise ValidationError("Only pending requests can be reviewed.")
    if leave.employee.user_id == reviewer.pk:
        raise PermissionDenied("You cannot review your own leave request.")
    if not has_role(reviewer, *PRIVILEGED_ROLES):
        raise PermissionDenied("Only managers and owners can review leave.")
    if has_role(leave.employee.user, *PRIVILEGED_ROLES) and not has_role(reviewer, OWNER):
        raise PermissionDenied("Only an owner can review a manager's leave.")
    leave.status = LeaveRequest.Status.APPROVED if approve else LeaveRequest.Status.REJECTED
    leave.reviewed_by, leave.reviewed_at, leave.review_note = reviewer, timezone.now(), note
    leave.save()
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
