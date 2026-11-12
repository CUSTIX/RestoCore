"""Booking rules: opening hours, slot capacity and the status workflow."""

import datetime as dt

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Sum
from django.utils import timezone

from bookings.models import Booking
from core import throttle

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


def has_started(booking: Booking, now=None) -> bool:
    """True once the booking's date and time have arrived (local time)."""
    now = now or timezone.localtime()
    return (booking.date, booking.time) <= (now.date(), now.time().replace(tzinfo=None))


def allowed_transitions(booking: Booking, now=None) -> tuple[str, ...]:
    """Status changes that make sense right now, not just in the abstract workflow:
    you confirm before the time, seat guests on the day, and mark a no-show once it has passed."""
    now = now or timezone.localtime()
    started = has_started(booking, now)
    allowed = []
    for status in TRANSITIONS.get(booking.status, ()):
        if status == Booking.Status.CONFIRMED and started:
            continue  # too late to confirm a request: cancel it instead
        if status == Booking.Status.SEATED and booking.date != now.date():
            continue  # guests are seated on the day of the booking
        if status == Booking.Status.NO_SHOW and not started:
            continue  # nobody can be a no-show before the booking time
        allowed.append(status)
    return tuple(allowed)


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
def _lock_slot(date: dt.date, time: dt.time) -> None:
    """Serialise bookings for one slot, even when the slot has no rows yet.

    A Postgres transaction-level advisory lock keyed on the slot (e.g. 202611121930).
    It is released automatically at commit/rollback. Row locks alone cannot protect an
    empty slot, so two first bookings could otherwise both pass the capacity check.
    """
    key = int(date.strftime("%Y%m%d")) * 10_000 + time.hour * 100 + time.minute
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [key])


@transaction.atomic
def create_booking(*, source: str = Booking.Source.WEBSITE, **data) -> Booking:
    _lock_slot(data["date"], data["time"])
    validate_slot(date=data["date"], time=data["time"], party_size=data["party_size"])
    return Booking.objects.create(source=source, **data)


# Public form limits per visitor IP: stops a bot from filling every slot and turning real guests
# away. Generous for people; phone bookings by staff are not limited.
PUBLIC_BOOKINGS_PER_HOUR = 3
PUBLIC_BOOKINGS_PER_DAY = 10
TOO_MANY_BOOKINGS = (
    "You've made several bookings in a short time. Please call us and we'll sort out the rest."
)


def create_public_booking(*, ip: str | None, **data) -> Booking:
    """A booking from the website form, rate limited per visitor IP."""
    if ip is not None and (
        throttle.is_limited(
            "booking-ip", ip, limit=PUBLIC_BOOKINGS_PER_HOUR, window=dt.timedelta(hours=1)
        )
        or throttle.is_limited(
            "booking-ip", ip, limit=PUBLIC_BOOKINGS_PER_DAY, window=dt.timedelta(days=1)
        )
    ):
        raise ValidationError(TOO_MANY_BOOKINGS)
    booking = create_booking(source=Booking.Source.WEBSITE, **data)
    if ip is not None:
        throttle.record("booking-ip", ip)
    return booking


@transaction.atomic
def update_booking(booking: Booking, **data) -> Booking:
    # Re-read under lock: the caller's copy may be stale or already modified by a form.
    current = Booking.objects.select_for_update().get(pk=booking.pk)
    if current.status not in (Booking.Status.PENDING, Booking.Status.CONFIRMED):
        raise ValidationError("Only pending or confirmed bookings can be edited.")
    booking = current
    moved = (data["date"], data["time"]) != (booking.date, booking.time)
    if moved or data["party_size"] > booking.party_size:
        # Only a new slot (or more seats) needs the slot rules. Fixing a phone number or notes on
        # a booking whose time has already started must not fail with "time has passed".
        _lock_slot(data["date"], data["time"])
        if moved:
            validate_slot(
                date=data["date"],
                time=data["time"],
                party_size=data["party_size"],
                exclude_id=booking.pk,
            )
        else:
            remaining = SLOT_CAPACITY - seats_taken(booking.date, booking.time, booking.pk)
            if data["party_size"] > MAX_PARTY_SIZE or data["party_size"] > remaining:
                raise ValidationError(f"Only {min(remaining, MAX_PARTY_SIZE)} seats are left.")
    for field, value in data.items():
        setattr(booking, field, value)
    booking.save()
    return booking


@transaction.atomic
def change_status(booking: Booking, new_status: str) -> Booking:
    booking = Booking.objects.select_for_update().get(pk=booking.pk)
    if new_status == booking.status:
        return booking  # double-click / second tab: already done, not an error
    if new_status not in allowed_transitions(booking):
        timing = {
            Booking.Status.CONFIRMED: "This booking's time has passed, so it can't be confirmed.",
            Booking.Status.SEATED: "Guests can only be seated on the day of the booking.",
            Booking.Status.NO_SHOW: "It can only be a no-show once the booking time has passed.",
        }
        if new_status in TRANSITIONS.get(booking.status, ()) and new_status in timing:
            raise ValidationError(timing[new_status])
        raise ValidationError(
            f"Cannot change a {booking.get_status_display().lower()} booking to "
            f"{Booking.Status(new_status).label.lower()}."
        )
    booking.status = new_status
    booking.save(update_fields=["status", "updated_at"])
    return booking
