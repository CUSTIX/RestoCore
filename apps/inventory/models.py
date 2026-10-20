from decimal import Decimal

from django.db import models

from apps.core.models import TimeStampedModel


class InventoryItem(TimeStampedModel):
    class Kind(models.TextChoices):
        INGREDIENT = "ingredient", "Ingredient"
        UTENSIL = "utensil", "Utensil"
        DECORATION = "decoration", "Decoration"

    name = models.CharField(max_length=160)
    sku = models.CharField(max_length=64, unique=True)
    kind = models.CharField(max_length=16, choices=Kind.choices, db_index=True)
    unit = models.CharField(max_length=24, default="piece")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self) -> str:
        return self.name


class StockMovement(TimeStampedModel):
    class Type(models.TextChoices):
        RECEIPT = "receipt", "Receipt"
        USAGE = "usage", "Usage"
        ADJUSTMENT = "adjustment", "Adjustment"
        DAMAGE = "damage", "Damage"
        RETURN = "return", "Return"

    item = models.ForeignKey(
        InventoryItem,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField(max_length=16, choices=Type.choices, db_index=True)
    quantity_delta = models.DecimalField(max_digits=14, decimal_places=3)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(quantity_delta=0),
                name="stock_movement_quantity_nonzero",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.quantity_delta >= Decimal("0") else ""
        return f"{self.item} {sign}{self.quantity_delta}"


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
