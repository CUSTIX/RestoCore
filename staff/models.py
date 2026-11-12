from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class Employee(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="employee"
    )
    position = models.CharField(max_length=80)
    phone = models.CharField(max_length=32, blank=True)
    hourly_rate = models.DecimalField(max_digits=8, decimal_places=2)
    hire_date = models.DateField()
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ("user__first_name", "user__last_name", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(hourly_rate__gte=0),
                name="employee_rate_not_negative",
                violation_error_message="The hourly rate can't be negative.",
            ),
        ]

    def __str__(self) -> str:
        return str(self.user)


class Shift(TimeStampedModel):
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="shifts")
    date = models.DateField(db_index=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    note = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ("date", "start_time", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_time__gt=models.F("start_time")),
                name="shift_ends_after_start",
                violation_error_message="The shift must end after it starts.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.date} {self.start_time:%H:%M}-{self.end_time:%H:%M}"

    @property
    def hours(self) -> Decimal:
        minutes = (self.end_time.hour * 60 + self.end_time.minute) - (
            self.start_time.hour * 60 + self.start_time.minute
        )
        return (Decimal(minutes) / Decimal(60)).quantize(Decimal("0.01"))


class TimeEntry(models.Model):
    """One clock-in / clock-out pair."""

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="time_entries")
    clock_in = models.DateTimeField(db_index=True)
    clock_out = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-clock_in", "-id")
        verbose_name_plural = "time entries"
        constraints = [
            models.UniqueConstraint(
                fields=["employee"],
                condition=models.Q(clock_out__isnull=True),
                name="one_open_time_entry_per_employee",
            ),
            models.CheckConstraint(
                condition=models.Q(clock_out__isnull=True)
                | models.Q(clock_out__gt=models.F("clock_in")),
                name="clock_out_after_clock_in",
                violation_error_message="The clock-out must be after the clock-in.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.clock_in:%Y-%m-%d %H:%M}"

    @property
    def hours(self) -> Decimal | None:
        if not self.clock_out:
            return None
        seconds = Decimal((self.clock_out - self.clock_in).total_seconds())
        return (seconds / Decimal(3600)).quantize(Decimal("0.01"))


class LeaveRequest(TimeStampedModel):
    class LeaveType(models.TextChoices):
        VACATION = "vacation", "Vacation"
        SICK = "sick", "Sick"
        PERSONAL = "personal", "Personal"
        UNPAID = "unpaid", "Unpaid"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=10, choices=LeaveType.choices)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.CharField(max_length=300, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ("-start_date", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="leave_end_not_before_start",
                violation_error_message="The leave can't end before it starts.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee} · {self.leave_type} {self.start_date}–{self.end_date}"

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1
