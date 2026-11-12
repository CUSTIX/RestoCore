"""Leave, shifts, attendance and deactivation must keep the schedule and pay consistent."""

import datetime as dt

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from staff import services
from staff.models import LeaveRequest, Shift, TimeEntry

T9, T17 = dt.time(9, 0), dt.time(17, 0)


def day(n):
    return timezone.localdate() + dt.timedelta(days=n)


def shift(employee, n):
    return Shift.objects.create(employee=employee, date=day(n), start_time=T9, end_time=T17)


def pending_leave(employee, first, last):
    return LeaveRequest.objects.create(
        employee=employee, leave_type="vacation", start_date=day(first), end_date=day(last)
    )


# ---- leave vs. schedule --------------------------------------------------------------------


@pytest.mark.django_db
def test_approving_leave_removes_the_shifts_on_those_days(make_employee, make_user):
    emp = make_employee()
    during, after = shift(emp, 3), shift(emp, 9)
    leave = services.review_leave(
        pending_leave(emp, 2, 5), reviewer=make_user("Manager"), approve=True
    )
    assert leave.removed_shifts == 1
    assert not Shift.objects.filter(pk=during.pk).exists()
    assert Shift.objects.filter(pk=after.pk).exists()


@pytest.mark.django_db
def test_rejecting_leave_keeps_the_schedule(make_employee, make_user):
    emp = make_employee()
    s = shift(emp, 3)
    services.review_leave(pending_leave(emp, 2, 5), reviewer=make_user("Manager"), approve=False)
    assert Shift.objects.filter(pk=s.pk).exists()


@pytest.mark.django_db
def test_leave_list_only_offers_review_buttons_the_reviewer_may_use(client_for, make_employee):
    """A manager saw Approve/Reject on another manager's request, then got an error."""
    managers_leave = pending_leave(make_employee(role="Manager"), 3, 4)
    staff_leave = pending_leave(make_employee(role="Staff"), 3, 4)
    shift(staff_leave.employee, 3)
    html = client_for("Manager").get("/app/staff/leave/").content.decode()
    assert f"/app/staff/leave/{staff_leave.pk}/review/" in html
    assert f"/app/staff/leave/{managers_leave.pk}/review/" not in html
    assert "reviewed by the owner" in html
    assert "Approving removes 1 scheduled shift" in html


# ---- shifts --------------------------------------------------------------------------------


@pytest.mark.django_db
def test_new_shifts_cannot_be_put_on_a_past_day(make_employee):
    with pytest.raises(ValidationError, match="already passed"):
        services.save_shift(employee=make_employee(), date=day(-1), start_time=T9, end_time=T17)


@pytest.mark.django_db
def test_an_existing_past_shift_can_still_be_corrected_in_place(make_employee):
    emp = make_employee()
    past = shift(emp, -2)
    services.save_shift(
        shift=past, employee=emp, date=past.date, start_time=T9, end_time=dt.time(15, 0)
    )
    past.refresh_from_db()
    assert past.end_time == dt.time(15, 0)


# ---- deactivation --------------------------------------------------------------------------


@pytest.mark.django_db
def test_deactivating_clears_the_future_but_keeps_history(make_employee, make_user):
    emp = make_employee(role="Staff")
    past, future = shift(emp, -3), shift(emp, 4)
    leave = pending_leave(emp, 6, 7)
    updated = services.update_employee(
        emp,
        actor=make_user("Owner"),
        role="Staff",
        first_name="A",
        last_name="B",
        email="",
        position="Server",
        phone="",
        hourly_rate=emp.hourly_rate,
        hire_date=emp.hire_date,
        is_active=False,
    )
    assert updated.cleanup == {"shifts": 1, "leave": 1}
    assert Shift.objects.filter(pk=past.pk).exists()
    assert not Shift.objects.filter(pk=future.pk).exists()
    leave.refresh_from_db()
    assert leave.status == LeaveRequest.Status.CANCELLED


# ---- forgotten clock-outs ------------------------------------------------------------------


def open_entry(emp, hours_ago):
    return TimeEntry.objects.create(
        employee=emp, clock_in=timezone.now() - dt.timedelta(hours=hours_ago)
    )


@pytest.mark.django_db
def test_clocking_out_a_day_old_entry_is_refused(make_employee):
    """Otherwise a forgotten clock-out becomes a paid 28-hour shift."""
    emp = make_employee()
    open_entry(emp, 28)
    with pytest.raises(ValidationError, match="never closed"):
        services.clock_out(emp)
    with pytest.raises(ValidationError, match="Ask a manager"):
        services.clock_in(emp)


@pytest.mark.django_db
def test_a_normal_shift_clocks_out_fine(make_employee):
    emp = make_employee()
    open_entry(emp, 7)
    assert services.clock_out(emp).hours > 6


@pytest.mark.django_db
def test_manager_closes_a_forgotten_entry_with_the_real_time(make_employee, make_user):
    emp = make_employee()
    entry = open_entry(emp, 28)
    closed = services.close_entry(
        entry, at=entry.clock_in + dt.timedelta(hours=8), by=make_user("Manager")
    )
    assert closed.hours == 8
    services.clock_in(emp)  # and they can work again


@pytest.mark.django_db
@pytest.mark.parametrize(
    "offset,message",
    [
        (dt.timedelta(minutes=-5), "after the clock-in"),
        (dt.timedelta(hours=20), "longer than"),
    ],
)
def test_close_entry_rejects_impossible_times(make_employee, make_user, offset, message):
    entry = open_entry(make_employee(), 30)
    with pytest.raises(ValidationError, match=message):
        services.close_entry(entry, at=entry.clock_in + offset, by=make_user("Manager"))


@pytest.mark.django_db
def test_close_entry_rejects_the_future(make_employee, make_user):
    entry = open_entry(make_employee(), 2)
    with pytest.raises(ValidationError, match="future"):
        services.close_entry(
            entry, at=timezone.now() + dt.timedelta(hours=1), by=make_user("Manager")
        )


@pytest.mark.django_db
def test_only_management_can_close_entries(make_employee, make_user, client_for):
    entry = open_entry(make_employee(), 28)
    with pytest.raises(PermissionDenied):
        services.close_entry(
            entry, at=entry.clock_in + dt.timedelta(hours=8), by=make_user("Staff")
        )
    url = f"/app/staff/attendance/{entry.pk}/close/"
    assert client_for("Staff").post(url, {"clock_out": "2026-01-01T10:00"}).status_code == 403


@pytest.mark.django_db
def test_attendance_page_offers_closing_open_entries(client_for, make_employee):
    entry = open_entry(make_employee(), 28)
    html = client_for("Manager").get("/app/staff/attendance/").content.decode()
    assert f"/app/staff/attendance/{entry.pk}/close/" in html
    assert "Forgot to clock out?" in html
