from decimal import Decimal

from django.db.models import Count, QuerySet, Sum

from payroll.models import DeductionRate, PayPeriod, Payslip


def periods() -> QuerySet[PayPeriod]:
    return PayPeriod.objects.annotate(
        slip_count=Count("payslips"),
        total_net=Sum("payslips__net_pay"),
        total_gross=Sum("payslips__gross_pay"),
    ).order_by("-start_date")


def period_totals(period: PayPeriod) -> dict:
    agg = period.payslips.aggregate(
        gross=Sum("gross_pay"),
        deductions=Sum("total_deductions"),
        net=Sum("net_pay"),
        hours=Sum("hours_worked"),
    )
    return {k: v or Decimal("0") for k, v in agg.items()}


def payslips_for(period: PayPeriod) -> QuerySet[Payslip]:
    return period.payslips.prefetch_related("deductions").order_by("employee_name")


def deduction_rates() -> QuerySet[DeductionRate]:
    return DeductionRate.objects.order_by("name")
