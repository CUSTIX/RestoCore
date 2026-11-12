"""DEMO payroll. Rates are placeholders, not any country's real rules. See README."""

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

MONEY = {"max_digits": 12, "decimal_places": 2}


class DeductionRate(models.Model):
    name = models.CharField(max_length=80, unique=True)
    rate = models.DecimalField(
        max_digits=5, decimal_places=4, help_text="Fraction of gross pay, e.g. 0.0450 = 4.5%."
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rate__gte=0) & models.Q(rate__lt=1),
                name="deduction_rate_between_0_and_1",
                # %% because Django %-formats constraint messages.
                violation_error_message="Enter the rate as a fraction below 1: 0.08 means 8%%.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.rate:.2%})"


class PayPeriod(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"

    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-start_date",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="pay_period_end_not_before_start",
                violation_error_message="The period can't end before it starts.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.start_date:%b %d} – {self.end_date:%b %d, %Y}"


class Payslip(models.Model):
    period = models.ForeignKey(PayPeriod, on_delete=models.CASCADE, related_name="payslips")
    employee = models.ForeignKey("staff.Employee", on_delete=models.PROTECT, related_name="+")
    employee_name = models.CharField(max_length=200)  # snapshot
    position = models.CharField(max_length=80)  # snapshot
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)  # snapshot
    hours_worked = models.DecimalField(max_digits=7, decimal_places=2)
    paid_leave_days = models.PositiveSmallIntegerField(default=0)
    regular_pay = models.DecimalField(**MONEY)
    leave_pay = models.DecimalField(**MONEY)
    gross_pay = models.DecimalField(**MONEY)
    total_deductions = models.DecimalField(**MONEY)
    net_pay = models.DecimalField(**MONEY)

    class Meta:
        ordering = ("employee_name",)
        constraints = [
            models.UniqueConstraint(fields=["period", "employee"], name="one_payslip_per_period"),
        ]

    def __str__(self) -> str:
        return f"{self.employee_name} · {self.period}"


class PayslipDeduction(models.Model):
    payslip = models.ForeignKey(Payslip, on_delete=models.CASCADE, related_name="deductions")
    name = models.CharField(max_length=80)
    rate = models.DecimalField(max_digits=5, decimal_places=4)
    amount = models.DecimalField(**MONEY)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name}: {self.amount}"
