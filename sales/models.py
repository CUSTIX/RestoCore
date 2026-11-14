import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

MONEY = {"max_digits": 10, "decimal_places": 2}


class MenuCategory(models.Model):
    name = models.CharField(max_length=60, unique=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "name")
        verbose_name_plural = "menu categories"

    def __str__(self) -> str:
        return self.name


class MenuItem(TimeStampedModel):
    category = models.ForeignKey(MenuCategory, on_delete=models.PROTECT, related_name="items")
    name = models.CharField(max_length=120, unique=True)
    description = models.CharField(max_length=255, blank=True)
    price = models.DecimalField(**MONEY)
    is_available = models.BooleanField(default=True, help_text="Untick to hide from menu and POS.")
    is_signature = models.BooleanField(
        default=False, help_text="Feature this dish on the home page."
    )
    # A path inside static files (e.g. "website/img/dishes/carbonara.jpg"). Photos ship with the
    # code instead of being uploaded, so the web container keeps no local state.
    photo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ("category__sort_order", "name")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name="menu_price_positive",
                violation_error_message="The price must be more than zero.",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class RecipeLine(models.Model):
    """How much of an inventory item one portion of a menu item uses."""

    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name="recipe")
    inventory_item = models.ForeignKey(
        "inventory.InventoryItem", on_delete=models.PROTECT, related_name="+"
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["menu_item", "inventory_item"], name="recipe_line_unique_ingredient"
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="recipe_quantity_positive",
                violation_error_message="Each ingredient needs a quantity above zero.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.menu_item}: {self.quantity} of {self.inventory_item_id}"


class Order(models.Model):
    class Status(models.TextChoices):
        PAID = "paid", "Paid"
        VOIDED = "voided", "Voided"

    class KitchenStatus(models.TextChoices):
        QUEUED = "queued", "Queued"
        PREPARING = "preparing", "Preparing"
        READY = "ready", "Ready"
        SERVED = "served", "Served"
        CANCELLED = "cancelled", "Cancelled"

    class OrderType(models.TextChoices):
        DINE_IN = "dine_in", "Dine-in"
        TAKEAWAY = "takeaway", "Takeaway"

    class PaymentMethod(models.TextChoices):
        CASH = "cash", "Cash"
        CARD = "card", "Card (recorded only)"

    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.PAID, db_index=True
    )
    kitchen_status = models.CharField(
        max_length=10, choices=KitchenStatus.choices, default=KitchenStatus.QUEUED, db_index=True
    )
    order_type = models.CharField(max_length=10, choices=OrderType.choices)
    table_label = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=6, choices=PaymentMethod.choices)
    subtotal = models.DecimalField(**MONEY)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=Decimal("0"))
    tax = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    amount_tendered = models.DecimalField(**MONEY)
    change_due = models.DecimalField(**MONEY)
    cashier = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders_taken"
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="orders_voided",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=200, blank=True)
    # One-time token from the POS screen that created this order. A double-click, refresh or
    # retry sends the same token again and gets this order back instead of a second charge.
    checkout_token = models.UUIDField(null=True, blank=True, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")

    def __str__(self) -> str:
        return self.number

    @property
    def number(self) -> str:
        return f"#{self.pk:05d}" if self.pk else "#new"

    @property
    def stock_reference(self) -> str:
        return f"ORDER-{self.pk}"


class OrderLine(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=120)  # snapshot: menu names can change later
    unit_price = models.DecimalField(**MONEY)  # snapshot: prices can change later
    quantity = models.PositiveSmallIntegerField()
    line_total = models.DecimalField(**MONEY)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.quantity} × {self.name}"


class SelfOrder(models.Model):
    """An order a customer placed on their phone after scanning a table QR code.

    It is not a sale yet: nothing is charged and no stock moves. The customer tells the cashier
    the short `code`; the cashier opens it in the POS, checks it with them, takes payment, and
    only then does the real `Order` exist (and reach the kitchen).
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Waiting to pay"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    # Short and easy to say out loud. Unique only among open orders, so codes can be reused.
    code = models.CharField(max_length=8, db_index=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    order_type = models.CharField(max_length=10, choices=Order.OrderType.choices)
    table_label = models.CharField(max_length=20, blank=True)
    # Estimate shown to the customer. The POS re-prices everything when the cashier charges.
    subtotal = models.DecimalField(**MONEY)
    tax = models.DecimalField(**MONEY)
    total = models.DecimalField(**MONEY)
    # Unguessable: the customer's status link, and the POS checkout token (charging twice is
    # impossible: a second charge finds the order the first one created).
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    order = models.OneToOneField(
        Order, null=True, blank=True, on_delete=models.PROTECT, related_name="self_order"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=models.Q(status="pending"),
                name="self_order_open_code_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.code


class SelfOrderLine(models.Model):
    self_order = models.ForeignKey(SelfOrder, on_delete=models.CASCADE, related_name="lines")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="+")
    name = models.CharField(max_length=120)
    unit_price = models.DecimalField(**MONEY)
    quantity = models.PositiveSmallIntegerField()
    line_total = models.DecimalField(**MONEY)

    class Meta:
        ordering = ("id",)

    def __str__(self) -> str:
        return f"{self.quantity} × {self.name}"
