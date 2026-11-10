import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from staff import services
from staff.models import LeaveRequest

T = dt.time


def test_clock_in_and_out(make_employee):
    emp = make_employee()
    entry = services.clock_in(emp, at=timezone.now() - dt.timedelta(hours=8))
    with pytest.raises(ValidationError, match="already clocked in"):
        services.clock_in(emp)
    entry = services.clock_out(emp)
    assert entry.hours >= Decimal("7.99")
    with pytest.raises(ValidationError, match="not clocked in"):
        services.clock_out(emp)


def test_inactive_employee_cannot_clock_in(make_employee):
    emp = make_employee(is_active=False)
    with pytest.raises(ValidationError):
        services.clock_in(emp)


def test_shift_overlap_rejected(make_employee, tomorrow):
    emp = make_employee()
    services.save_shift(employee=emp, date=tomorrow, start_time=T(10), end_time=T(16))
    with pytest.raises(ValidationError, match="overlaps"):
        services.save_shift(employee=emp, date=tomorrow, start_time=T(15), end_time=T(20))
    services.save_shift(employee=emp, date=tomorrow, start_time=T(16), end_time=T(20))  # touching


def test_shift_must_end_after_start(make_employee, tomorrow):
    with pytest.raises(ValidationError):
        services.save_shift(
            employee=make_employee(), date=tomorrow, start_time=T(18), end_time=T(9)
        )


def test_cannot_schedule_on_approved_leave(make_employee, make_user, tomorrow):
    emp = make_employee()
    leave = services.request_leave(
        emp, leave_type="vacation", start_date=tomorrow, end_date=tomorrow
    )
    services.review_leave(leave, reviewer=make_user("Manager"), approve=True)
    with pytest.raises(ValidationError, match="leave"):
        services.save_shift(employee=emp, date=tomorrow, start_time=T(9), end_time=T(17))


def test_leave_rules(make_employee, tomorrow):
    emp = make_employee()
    with pytest.raises(ValidationError, match="before the start"):
        services.request_leave(
            emp, leave_type="sick", start_date=tomorrow, end_date=tomorrow - dt.timedelta(days=1)
        )
    with pytest.raises(ValidationError, match="past"):
        services.request_leave(
            emp,
            leave_type="sick",
            start_date=timezone.localdate() - dt.timedelta(days=2),
            end_date=tomorrow,
        )
    services.request_leave(
        emp, leave_type="vacation", start_date=tomorrow, end_date=tomorrow + dt.timedelta(days=2)
    )
    with pytest.raises(ValidationError, match="already have"):
        services.request_leave(
            emp,
            leave_type="personal",
            start_date=tomorrow + dt.timedelta(days=1),
            end_date=tomorrow + dt.timedelta(days=4),
        )


def test_cannot_review_own_leave(make_employee, make_user, tomorrow):
    manager = make_user("Manager")
    emp = make_employee(user=manager)
    leave = services.request_leave(
        emp, leave_type="vacation", start_date=tomorrow, end_date=tomorrow
    )
    with pytest.raises(PermissionDenied, match="own"):
        services.review_leave(leave, reviewer=manager, approve=True)


def test_manager_cannot_review_another_managers_leave(make_employee, make_user, tomorrow):
    emp = make_employee(role="Manager")
    leave = services.request_leave(
        emp, leave_type="vacation", start_date=tomorrow, end_date=tomorrow
    )
    with pytest.raises(PermissionDenied, match="owner"):
        services.review_leave(leave, reviewer=make_user("Manager"), approve=True)
    leave = services.review_leave(leave, reviewer=make_user("Owner"), approve=False, note="no")
    assert leave.status == LeaveRequest.Status.REJECTED


def test_reviewed_leave_cannot_be_reviewed_again_or_cancelled(make_employee, make_user, tomorrow):
    emp = make_employee()
    leave = services.request_leave(
        emp, leave_type="vacation", start_date=tomorrow, end_date=tomorrow
    )
    services.review_leave(leave, reviewer=make_user("Manager"), approve=True)
    with pytest.raises(ValidationError):
        services.review_leave(leave, reviewer=make_user("Owner"), approve=False)
    with pytest.raises(ValidationError):
        services.cancel_leave(leave, employee=emp)


def test_manager_cannot_create_owner_or_manager(make_user):
    manager = make_user("Manager")
    for role in ("Owner", "Manager"):
        with pytest.raises(PermissionDenied):
            services.create_employee(
                actor=manager,
                username=f"x{role}",
                password="long-password-1",
                first_name="A",
                last_name="B",
                email="",
                role=role,
                position="x",
                phone="",
                hourly_rate=Decimal("1"),
                hire_date=dt.date(2024, 1, 1),
            )


def test_manager_creates_staff_and_duplicate_username_fails(make_user):
    manager = make_user("Manager")
    kwargs = {
        "actor": manager,
        "username": "newbie",
        "password": "long-password-1",
        "first_name": "New",
        "last_name": "Bie",
        "email": "",
        "role": "Staff",
        "position": "Server",
        "phone": "",
        "hourly_rate": Decimal("100"),
        "hire_date": dt.date(2024, 1, 1),
    }
    emp = services.create_employee(**kwargs)
    assert emp.user.check_password("long-password-1")
    with pytest.raises(ValidationError, match="taken"):
        services.create_employee(**kwargs)


def test_deactivating_employee_blocks_login(make_employee, make_user):
    owner = make_user("Owner")
    emp = make_employee(role="Staff")
    services.update_employee(
        emp,
        actor=owner,
        role="Staff",
        first_name="A",
        last_name="B",
        email="",
        position="x",
        phone="",
        hourly_rate=Decimal("1"),
        hire_date=dt.date(2024, 1, 1),
        is_active=False,
    )
    emp.user.refresh_from_db()
    assert emp.user.is_active is False


def test_cannot_deactivate_or_demote_yourself(make_employee, make_user):
    owner = make_user("Owner")
    emp = make_employee(user=owner)
    base = {
        "first_name": "A",
        "last_name": "B",
        "email": "",
        "position": "x",
        "phone": "",
        "hourly_rate": Decimal("1"),
        "hire_date": dt.date(2024, 1, 1),
    }
    with pytest.raises(ValidationError, match="deactivate"):
        services.update_employee(emp, actor=owner, role="Owner", is_active=False, **base)
    with pytest.raises(ValidationError, match="role"):
        services.update_employee(emp, actor=owner, role="Staff", is_active=True, **base)
