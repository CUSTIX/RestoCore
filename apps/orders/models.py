from django.db import models


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_orders", "Can access orders"),
            ("manage_orders", "Can manage orders"),
            ("void_order", "Can void orders"),
        ]

    def __str__(self) -> str:
        return "Orders access"
