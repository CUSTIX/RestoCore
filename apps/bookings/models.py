from django.db import models


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_bookings", "Can access bookings"),
            ("manage_bookings", "Can manage bookings"),
        ]

    def __str__(self) -> str:
        return "Bookings access"
