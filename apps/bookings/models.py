from django.db import models

from apps.core.models import TimeStampedModel


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SEATED = "seated", "Seated"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    guest_name = models.CharField(max_length=150)
    guest_email = models.EmailField(blank=True)
    guest_phone = models.CharField(max_length=32, blank=True)
    party_size = models.PositiveSmallIntegerField()
    starts_at = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("starts_at", "id")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(party_size__gt=0),
                name="booking_party_size_gt_0",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.guest_name} - {self.starts_at:%Y-%m-%d %H:%M}"


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
