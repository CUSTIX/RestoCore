from django.db import models


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_reports", "Can access reports"),
        ]

    def __str__(self) -> str:
        return "Reports access"
