from django.contrib import admin

from staff.models import Employee, LeaveRequest, Shift, TimeEntry


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ("user", "position", "hourly_rate", "hire_date", "is_active")
    list_select_related = ("user",)
    search_fields = ("user__first_name", "user__last_name", "user__username")


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = ("employee", "date", "start_time", "end_time")
    list_filter = ("date",)
    list_select_related = ("employee__user",)


@admin.register(TimeEntry)
class TimeEntryAdmin(admin.ModelAdmin):
    """Attendance corrections are done here by an owner."""

    list_display = ("employee", "clock_in", "clock_out")
    list_select_related = ("employee__user",)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")
    list_filter = ("status", "leave_type")
    list_select_related = ("employee__user",)
