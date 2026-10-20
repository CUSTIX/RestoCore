from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.money import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS
from apps.staff.models import EmployeeProfile


class PayrollRun(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        FINALIZED = "finalized", "Finalized"

    period_start = models.DateField()
    period_end = models.DateField()
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    class Meta:
        ordering = ("-period_start", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(period_end__gte=models.F("period_start")),
                name="payroll_period_end_gte_start",
            ),
            models.UniqueConstraint(
                fields=("period_start", "period_end"),
                name="unique_payroll_period",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.period_start} to {self.period_end}"


class Payslip(TimeStampedModel):
    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.PROTECT,
        related_name="payslips",
    )
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="payslips",
    )
    gross_pay = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=0,
    )
    deductions = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=0,
    )
    net_pay = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
        default=0,
    )

    class Meta:
        ordering = ("employee__employee_code", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("payroll_run", "employee"),
                name="one_payslip_per_employee_per_run",
            ),
            models.CheckConstraint(
                condition=models.Q(gross_pay__gte=0),
                name="payslip_gross_pay_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(deductions__gte=0),
                name="payslip_deductions_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(net_pay__gte=0),
                name="payslip_net_pay_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} - {self.payroll_run}"


class PayslipLine(TimeStampedModel):
    class Kind(models.TextChoices):
        EARNING = "earning", "Earning"
        DEDUCTION = "deduction", "Deduction"

    payslip = models.ForeignKey(
        Payslip,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    label = models.CharField(max_length=120)
    amount = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gte=0),
                name="payslip_line_amount_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.label}: {self.amount}"


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_payroll", "Can access payroll"),
            ("run_payroll", "Can run payroll"),
        ]

    def __str__(self) -> str:
        return "Payroll access"
