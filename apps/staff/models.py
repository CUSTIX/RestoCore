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
