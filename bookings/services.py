"""Booking rules: opening hours, slot capacity and the status workflow."""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from bookings.models import Booking

OPENING_TIME = dt.time(11, 0)
LAST_SEATING = dt.time(21, 0)
SLOT_MINUTES = 30
SLOT_CAPACITY = 40  # max guests that can start in the same 30-minute slot
MAX_PARTY_SIZE = 20
MAX_DAYS_AHEAD = 90

# Statuses that hold a seat. Cancelled / no-show bookings free their seats.
ACTIVE_STATUSES = (
    Booking.Status.PENDING,
    Booking.Status.CONFIRMED,
    Booking.Status.SEATED,
    Booking.Status.COMPLETED,
)

TRANSITIONS = {
    Booking.Status.PENDING: (Booking.Status.CONFIRMED, Booking.Status.CANCELLED),
    Booking.Status.CONFIRMED: (
        Booking.Status.SEATED,
        Booking.Status.CANCELLED,
        Booking.Status.NO_SHOW,
    ),
    Booking.Status.SEATED: (Booking.Status.COMPLETED,),
    Booking.Status.COMPLETED: (),
    Booking.Status.CANCELLED: (),
    Booking.Status.NO_SHOW: (),
}


def time_slots() -> list[dt.time]:
    slots, current = [], dt.datetime.combine(dt.date.today(), OPENING_TIME)
    last = dt.datetime.combine(dt.date.today(), LAST_SEATING)
    while current <= last:
        slots.append(current.time())
        current += dt.timedelta(minutes=SLOT_MINUTES)
    return slots


def allowed_transitions(booking: Booking) -> tuple[str, ...]:
    return TRANSITIONS.get(booking.status, ())


def seats_taken(date: dt.date, time: dt.time, exclude_id: int | None = None) -> int:
    qs = Booking.objects.filter(date=date, time=time, status__in=ACTIVE_STATUSES)
    if exclude_id:
        qs = qs.exclude(pk=exclude_id)
    return qs.aggregate(total=Sum("party_size"))["total"] or 0


def validate_slot(*, date: dt.date, time: dt.time, party_size: int, exclude_id=None) -> None:
    """Raise ValidationError if the booking cannot be accepted."""
    now = timezone.localtime()
    if party_size < 1 or party_size > MAX_PARTY_SIZE:
        raise ValidationError(f"Party size must be between 1 and {MAX_PARTY_SIZE}.")
    if time not in time_slots():
        raise ValidationError("Please choose one of the available times.")
    if date < now.date() or (date == now.date() and time <= now.time()):
        raise ValidationError("That time has already passed. Please choose a future time.")
    if date > now.date() + dt.timedelta(days=MAX_DAYS_AHEAD):
        raise ValidationError(f"Bookings open up to {MAX_DAYS_AHEAD} days ahead.")
    remaining = SLOT_CAPACITY - seats_taken(date, time, exclude_id=exclude_id)
    if party_size > remaining:
        if remaining <= 0:
            raise ValidationError("That time is fully booked. Please choose another time.")
        raise ValidationError(f"Only {remaining} seats are left at that time.")


@transaction.atomic
def create_booking(*, source: str = Booking.Source.WEBSITE, **data) -> Booking:
    # Lock the slot's rows so two simultaneous requests cannot overbook it.
    list(
        Booking.objects.select_for_update()
        .filter(date=data["date"], time=data["time"])
        .values_list("pk", flat=True)
    )
    validate_slot(date=data["date"], time=data["time"], party_size=data["party_size"])
    return Booking.objects.create(source=source, **data)


@transaction.atomic
def update_booking(booking: Booking, **data) -> Booking:
    if booking.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED):
        raise ValidationError("Only pending or confirmed bookings can be edited.")
    validate_slot(
        date=data["date"], time=data["time"], party_size=data["party_size"], exclude_id=booking.pk
    )
    for field, value in data.items():
        setattr(booking, field, value)
    booking.save()
    return booking


@transaction.atomic
def change_status(booking: Booking, new_status: str) -> Booking:
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if new_status not in allowed_transitions(booking):
        raise ValidationError(
            f"Cannot change a {booking.get_status_display().lower()} booking to "
            f"{Booking.Status(new_status).label.lower()}."
        )
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])
    return booking
