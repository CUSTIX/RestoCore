from django.contrib import admin

from payroll.models import DeductionRate, PayPeriod, Payslip


@admin.register(DeductionRate)
class DeductionRateAdmin(admin.ModelAdmin):
    list_display = ("name", "rate", "is_active")


@admin.register(PayPeriod)
class PayPeriodAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "finalized_at")


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ("employee_name", "period", "hours_worked", "gross_pay", "net_pay")
    list_select_related = ("period",)

    def has_change_permission(self, request, obj=None):
        return False
