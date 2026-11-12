from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class InventoryItem(TimeStampedModel):
    class Unit(models.TextChoices):
        GRAM = "g", "grams"
        KILOGRAM = "kg", "kilograms"
        MILLILITRE = "ml", "millilitres"
        LITRE = "l", "litres"
        PIECE = "pcs", "pieces"

    name = models.CharField(max_length=120, unique=True)
    unit = models.CharField(max_length=4, choices=Unit.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal("0"))
    reorder_level = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
        help_text="Show a low-stock warning at or below this quantity.",
    )
    cost_per_unit = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=0),
                name="inventory_quantity_not_negative",
                violation_error_message="Stock on hand can't go below zero.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.unit})"

    @property
    def is_low(self) -> bool:
        return self.quantity <= self.reorder_level


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        PURCHASE = "purchase", "Stock received"
        SALE = "sale", "Used by sale"
        SALE_VOID = "sale_void", "Returned from voided sale"
        WASTE = "waste", "Waste / spoilage"
        COUNT = "count", "Stock count correction"

    item = models.ForeignKey(InventoryItem, on_delete=models.PROTECT, related_name="movements")
    change = models.DecimalField(max_digits=12, decimal_places=3)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=10, choices=Reason.choices, db_index=True)
    reference = models.CharField(max_length=40, blank=True, db_index=True)
    note = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return f"{self.item.name} {self.change:+} ({self.reason})"
