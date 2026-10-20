from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.money import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS, as_money


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        ONGOING = "ongoing", "Ongoing"
        SERVING = "serving", "Serving"
        SERVED = "served", "Served"
        CANCELLED = "cancelled", "Cancelled"

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.ONGOING,
        db_index=True,
    )

    class Meta:
        ordering = ("-created_at", "-id")

    @property
    def total(self):
        return as_money(sum((item.line_total for item in self.items.all()), start=0))

    def __str__(self) -> str:
        return f"Order #{self.pk or 'new'}"


class OrderItem(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    item_name = models.CharField(max_length=160)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
    )

    class Meta:
        ordering = ("id",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="order_item_quantity_gt_0",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_item_unit_price_gte_0",
            ),
        ]

    @property
    def line_total(self):
        return as_money(self.unit_price * self.quantity)

    def __str__(self) -> str:
        return f"{self.quantity} x {self.item_name}"


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
