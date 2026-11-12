import secrets

from django.db import models

from core.models import TimeStampedModel

REFERENCE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I confusion


def new_reference() -> str:
    return "".join(secrets.choice(REFERENCE_ALPHABET) for _ in range(8))


class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SEATED = "seated", "Seated"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No-show"

    class Source(models.TextChoices):
        WEBSITE = "website", "Website"
        STAFF = "staff", "Staff (phone / walk-in)"

    reference = models.CharField(max_length=8, unique=True, default=new_reference, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32)
    party_size = models.PositiveSmallIntegerField()
    date = models.DateField(db_index=True)
    time = models.TimeField()
    notes = models.TextField(blank=True, max_length=500)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.WEBSITE)

    class Meta:
        ordering = ("date", "time", "id")
        indexes = [models.Index(fields=["date", "time"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(party_size__gte=1),
                name="booking_party_size_positive",
                violation_error_message="Party size must be at least 1.",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.reference} · {self.name} · {self.date} {self.time:%H:%M}"
