from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class EmployeeProfile(TimeStampedModel):
    """Employment data kept separate from authentication identity."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_code = models.CharField(max_length=32, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("employee_code",)

    def __str__(self) -> str:
        return self.employee_code


class Shift(TimeStampedModel):
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name="shifts",
    )
    starts_at = models.DateTimeField(db_index=True)
    ends_at = models.DateTimeField(db_index=True)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("starts_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(ends_at__gt=models.F("starts_at")),
                name="shift_ends_after_start",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} {self.starts_at:%Y-%m-%d %H:%M}"


class AttendanceSession(TimeStampedModel):
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.PROTECT,
        related_name="attendance_sessions",
    )
    shift = models.ForeignKey(
        Shift,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_sessions",
    )
    clock_in_at = models.DateTimeField(db_index=True)
    clock_out_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-clock_in_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(clock_out_at__isnull=True)
                    | models.Q(clock_out_at__gt=models.F("clock_in_at"))
                ),
                name="attendance_clock_out_after_in",
            ),
            models.UniqueConstraint(
                fields=("employee",),
                condition=models.Q(clock_out_at__isnull=True),
                name="one_open_attendance_per_employee",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} clock-in {self.clock_in_at:%Y-%m-%d %H:%M}"


class BreakSession(TimeStampedModel):
    attendance = models.ForeignKey(
        AttendanceSession,
        on_delete=models.CASCADE,
        related_name="breaks",
    )
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("started_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(ended_at__isnull=True) | models.Q(ended_at__gt=models.F("started_at"))
                ),
                name="break_ends_after_start",
            ),
            models.UniqueConstraint(
                fields=("attendance",),
                condition=models.Q(ended_at__isnull=True),
                name="one_open_break_per_attendance",
            ),
        ]

    def __str__(self) -> str:
        return f"Break for {self.attendance}"


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_staff", "Can access staff management"),
            ("manage_employees", "Can manage employees"),
            ("manage_schedules", "Can manage schedules"),
            ("review_employee_requests", "Can review employee requests"),
            ("record_attendance", "Can record attendance"),
        ]

    def __str__(self) -> str:
        return "Staff access"
