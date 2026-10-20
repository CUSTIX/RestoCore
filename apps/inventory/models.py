from django.db import models


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_inventory", "Can access inventory"),
            ("manage_inventory", "Can manage inventory"),
            ("adjust_stock", "Can adjust stock"),
        ]

    def __str__(self) -> str:
        return "Inventory access"
