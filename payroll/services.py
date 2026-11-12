"""DEMO payroll calculation.

gross = hours worked × hourly rate + paid leave days × PAID_LEAVE_HOURS × hourly rate
deductions = gross × each active DeductionRate
net = gross − deductions
"""

from decimal import ROUND_HALF_UP, Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from payroll.models import DeductionRate, PayPeriod, Payslip, PayslipDeduction
from staff import selectors as staff_selectors

CENT = Decimal("0.01")
PAID_LEAVE_HOURS = Decimal("8")
MAX_PERIOD_DAYS = 31


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@transaction.atomic
def create_period(*, start_date, end_date, user) -> PayPeriod:
    if end_date < start_date:
        raise ValidationError("The end date cannot be before the start date.")
    if (end_date - start_date).days + 1 > MAX_PERIOD_DAYS:
        raise ValidationError(f"A pay period can be at most {MAX_PERIOD_DAYS} days.")
    if PayPeriod.objects.filter(start_date__lte=end_date, end_date__gte=start_date).exists():
        raise ValidationError("This period overlaps an existing pay period.")
    return PayPeriod.objects.create(start_date=start_date, end_date=end_date, created_by=user)


def calculate(
    *, hours: Decimal, leave_days: int, hourly_rate: Decimal, rates: list[DeductionRate]
) -> dict:
    regular = money(hours * hourly_rate)
    leave = money(Decimal(leave_days) * PAID_LEAVE_HOURS * hourly_rate)
    gross = regular + leave
    deductions = [(r.name, r.rate, money(gross * r.rate)) for r in rates]
    total = sum((amount for _, _, amount in deductions), Decimal("0"))
    return {
        "regular_pay": regular,
        "leave_pay": leave,
        "gross_pay": gross,
        "deductions": deductions,
        "total_deductions": total,
        "net_pay": gross - total,
    }


@transaction.atomic
def generate_payslips(period: PayPeriod) -> int:
    """(Re)build all payslips for a draft period. Returns how many were created."""
    period = PayPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != PayPeriod.Status.DRAFT:
        raise ValidationError("Finalized periods cannot be recalculated.")
    period.payslips.all().delete()
    hours = staff_selectors.hours_worked(period.start_date, period.end_date)
    leave = staff_selectors.approved_leave_days(period.start_date, period.end_date)
    rates = list(DeductionRate.objects.filter(is_active=True))
    count = 0
    # Everyone who worked or had paid leave in the period, including people deactivated since:
    # leaving the café doesn't cancel wages already earned.
    for employee in staff_selectors.employees_by_ids(set(hours) | set(leave)):
        worked, leave_days = hours.get(employee.pk, Decimal("0")), leave.get(employee.pk, 0)
        if not worked and not leave_days:
            continue
        result = calculate(
            hours=worked, leave_days=leave_days, hourly_rate=employee.hourly_rate, rates=rates
        )
        slip = Payslip.objects.create(
            period=period,
            employee=employee,
            employee_name=str(employee),
            position=employee.position,
            hourly_rate=employee.hourly_rate,
            hours_worked=worked,
            paid_leave_days=leave_days,
            regular_pay=result["regular_pay"],
            leave_pay=result["leave_pay"],
            gross_pay=result["gross_pay"],
            total_deductions=result["total_deductions"],
            net_pay=result["net_pay"],
        )
        PayslipDeduction.objects.bulk_create(
            [
                PayslipDeduction(payslip=slip, name=name, rate=rate, amount=amount)
                for name, rate, amount in result["deductions"]
            ]
        )
        count += 1
    return count


@transaction.atomic
def finalize_period(period: PayPeriod) -> PayPeriod:
    period = PayPeriod.objects.select_for_update().get(pk=period.pk)
    if period.status != PayPeriod.Status.DRAFT:
        raise ValidationError("This period is already finalized.")
    if not period.payslips.exists():
        raise ValidationError("Generate payslips before finalizing.")
    open_count = staff_selectors.open_entries_between(period.start_date, period.end_date).count()
    if open_count:
        # Finalizing locks the period: hours from an unclosed clock-in would never be paid.
        one = open_count == 1
        raise ValidationError(
            f"{open_count} clock-in{'' if one else 's'} in this period "
            f"{'has' if one else 'have'} no clock-out yet. Close {'it' if one else 'them'} "
            "under Attendance, recalculate, then finalize."
        )
    period.status = PayPeriod.Status.FINALIZED
    period.finalized_at = timezone.now()
    period.save(update_fields=["status", "finalized_at", "updated_at"])
    return period
