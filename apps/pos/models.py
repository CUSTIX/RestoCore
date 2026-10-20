from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel
from apps.core.money import MONEY_DECIMAL_PLACES, MONEY_MAX_DIGITS
from apps.orders.models import Order


class Payment(TimeStampedModel):
    class Method(models.TextChoices):
        CASH = "cash", "Cash"

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="payment",
    )
    method = models.CharField(max_length=16, choices=Method.choices, default=Method.CASH)
    amount_due = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
    )
    amount_tendered = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
    )
    change_due = models.DecimalField(
        max_digits=MONEY_MAX_DIGITS,
        decimal_places=MONEY_DECIMAL_PLACES,
    )
    receipt_number = models.CharField(max_length=40, unique=True, db_index=True)
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="processed_payments",
    )

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount_due__gte=0),
                name="payment_amount_due_gte_0",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_tendered__gte=models.F("amount_due")),
                name="payment_tendered_gte_due",
            ),
            models.CheckConstraint(
                condition=models.Q(change_due__gte=0),
                name="payment_change_due_gte_0",
            ),
        ]

    def __str__(self) -> str:
        return self.receipt_number


class ModuleAccess(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ("access_pos", "Can access point of sale"),
            ("take_payment", "Can take point-of-sale payments"),
        ]

    def __str__(self) -> str:
        return "POS access"
