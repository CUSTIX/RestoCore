from django.db import models


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
