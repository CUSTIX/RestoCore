from django.db import models


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
