from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.payroll.models import PayrollRun, Payslip, PayslipLine
from apps.staff.models import EmployeeProfile


@pytest.fixture
def employee():
    user = get_user_model().objects.create_user(
        email="payroll-employee@example.com",
        password="test-only-password",
    )
    return EmployeeProfile.objects.create(user=user, employee_code="EMP-2001")


@pytest.mark.django_db
def test_payroll_period_must_not_end_before_start():
    with pytest.raises(IntegrityError), transaction.atomic():
        PayrollRun.objects.create(
            period_start=date(2026, 10, 16),
            period_end=date(2026, 10, 15),
        )


@pytest.mark.django_db
def test_only_one_payroll_run_per_exact_period():
    PayrollRun.objects.create(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 15),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        PayrollRun.objects.create(
            period_start=date(2026, 10, 1),
            period_end=date(2026, 10, 15),
        )


@pytest.mark.django_db
def test_only_one_payslip_per_employee_per_run(employee):
    run = PayrollRun.objects.create(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 15),
    )
    Payslip.objects.create(payroll_run=run, employee=employee)

    with pytest.raises(IntegrityError), transaction.atomic():
        Payslip.objects.create(payroll_run=run, employee=employee)


@pytest.mark.django_db
def test_payroll_amounts_must_be_non_negative(employee):
    run = PayrollRun.objects.create(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 15),
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Payslip.objects.create(
            payroll_run=run,
            employee=employee,
            gross_pay=Decimal("-0.01"),
        )


@pytest.mark.django_db
def test_payslip_line_amount_must_be_non_negative(employee):
    run = PayrollRun.objects.create(
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 15),
    )
    payslip = Payslip.objects.create(payroll_run=run, employee=employee)

    with pytest.raises(IntegrityError), transaction.atomic():
        PayslipLine.objects.create(
            payslip=payslip,
            kind=PayslipLine.Kind.DEDUCTION,
            label="Invalid",
            amount=Decimal("-0.01"),
        )
