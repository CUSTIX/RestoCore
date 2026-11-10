import datetime as dt
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from payroll import services
from payroll.models import DeductionRate, PayPeriod
from staff.models import LeaveRequest, TimeEntry

D = Decimal
ACCESS = {"Owner": 200, "Manager": 403, "Cashier": 403, "Kitchen": 403, "Staff": 403}


def test_calculation_math():
    rates = [DeductionRate(name="A", rate=D("0.10")), DeductionRate(name="B", rate=D("0.05"))]
    r = services.calculate(hours=D("10"), leave_days=1, hourly_rate=D("100"), rates=rates)
    assert r["regular_pay"] == D("1000.00")
    assert r["leave_pay"] == D("800.00")
    assert r["gross_pay"] == D("1800.00")
    assert r["total_deductions"] == D("270.00")
    assert r["net_pay"] == D("1530.00")


@pytest.fixture
def period(make_user):
    start = timezone.localdate() - dt.timedelta(days=10)
    return services.create_period(
        start_date=start, end_date=start + dt.timedelta(days=6), user=make_user("Owner")
    )


def test_generate_payslips_from_attendance_and_leave(period, make_employee):
    DeductionRate.objects.all().delete()
    DeductionRate.objects.create(name="Demo", rate=D("0.10"))
    emp = make_employee(rate=D("100"))
    idle = make_employee(rate=D("100"))  # no hours, no leave → no payslip
    tz = timezone.get_current_timezone()
    start = dt.datetime.combine(period.start_date, dt.time(9), tzinfo=tz)
    TimeEntry.objects.create(employee=emp, clock_in=start, clock_out=start + dt.timedelta(hours=8))
    LeaveRequest.objects.create(
        employee=emp,
        leave_type="sick",
        status="approved",
        start_date=period.start_date + dt.timedelta(days=1),
        end_date=period.start_date + dt.timedelta(days=1),
    )
    LeaveRequest.objects.create(
        employee=emp,
        leave_type="unpaid",
        status="approved",
        start_date=period.start_date + dt.timedelta(days=2),
        end_date=period.start_date + dt.timedelta(days=2),
    )
    assert services.generate_payslips(period) == 1
    slip = period.payslips.get()
    assert slip.employee_id == emp.pk and idle.pk != slip.employee_id
    assert slip.hours_worked == D("8.00") and slip.paid_leave_days == 1  # unpaid not counted
    assert slip.gross_pay == D("1600.00") and slip.net_pay == D("1440.00")
    assert slip.deductions.get().amount == D("160.00")


def test_regenerate_replaces_payslips(period, make_employee):
    emp = make_employee()
    tz = timezone.get_current_timezone()
    start = dt.datetime.combine(period.start_date, dt.time(9), tzinfo=tz)
    TimeEntry.objects.create(employee=emp, clock_in=start, clock_out=start + dt.timedelta(hours=4))
    services.generate_payslips(period)
    services.generate_payslips(period)
    assert period.payslips.count() == 1


def test_finalize_locks_period(period, make_employee):
    with pytest.raises(ValidationError, match="Generate"):
        services.finalize_period(period)
    emp = make_employee()
    tz = timezone.get_current_timezone()
    start = dt.datetime.combine(period.start_date, dt.time(9), tzinfo=tz)
    TimeEntry.objects.create(employee=emp, clock_in=start, clock_out=start + dt.timedelta(hours=4))
    services.generate_payslips(period)
    services.finalize_period(period)
    with pytest.raises(ValidationError, match="Finalized"):
        services.generate_payslips(period)


def test_period_validation(period, make_user):
    owner = make_user("Owner")
    with pytest.raises(ValidationError, match="overlaps"):
        services.create_period(start_date=period.start_date, end_date=period.end_date, user=owner)
    with pytest.raises(ValidationError, match="before"):
        services.create_period(
            start_date=dt.date(2024, 2, 10), end_date=dt.date(2024, 2, 1), user=owner
        )
    with pytest.raises(ValidationError, match="at most"):
        services.create_period(
            start_date=dt.date(2024, 1, 1), end_date=dt.date(2024, 3, 1), user=owner
        )


@pytest.mark.django_db
def test_demo_rates_seeded_by_migration():
    assert DeductionRate.objects.filter(name__icontains="demo").count() == 4


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", ACCESS.items())
def test_payroll_is_owner_only(client_for, role, status):
    assert client_for(role).get("/app/payroll/").status_code == status


@pytest.mark.django_db
@pytest.mark.parametrize("role,status", ACCESS.items())
def test_period_actions_are_owner_only(client_for, period, role, status):
    response = client_for(role).post(
        f"/app/payroll/periods/{period.pk}/action/", {"action": "generate"}
    )
    assert response.status_code == (302 if status == 200 else 403)


@pytest.mark.django_db
def test_owner_creates_period_via_form(client_for):
    response = client_for("Owner").post(
        "/app/payroll/", {"start_date": "2024-01-01", "end_date": "2024-01-15"}
    )
    assert response.status_code == 302
    assert PayPeriod.objects.count() == 1
