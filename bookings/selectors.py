import datetime as dt

from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone

from bookings.models import Booking
from bookings.services import (
    ACTIVE_STATUSES,
    LAST_SEATING,
    MAX_DAYS_AHEAD,
    OPENING_TIME,
    SLOT_CAPACITY,
    time_slots,
)


def opening_hours() -> tuple[dt.time, dt.time]:
    return OPENING_TIME, LAST_SEATING


def _not_started() -> Q:
    """Bookings whose date and time are still ahead (local time)."""
    now = timezone.localtime()
    return Q(date__gt=now.date()) | Q(date=now.date(), time__gt=now.time().replace(tzinfo=None))


def _seated_today() -> Q:
    """Guests at a table right now. A booking still "seated" from an earlier day was simply
    never closed: it belongs with the past, not at the top of today's list."""
    return Q(status=Booking.Status.SEATED, date=timezone.localdate())


WHEN_UPCOMING, WHEN_PAST, WHEN_ALL = "upcoming", "past", "all"


def filter_bookings(
    *, date=None, status: str = "", q: str = "", when: str = WHEN_UPCOMING
) -> QuerySet[Booking]:
    """Staff list. Defaults to what's ahead, soonest first; past bookings newest first.
    Picking a date shows that whole day regardless of `when`."""
    qs = Booking.objects.all()
    if date:
        qs = qs.filter(date=date)
    elif when == WHEN_UPCOMING:
        # Still ahead, plus guests at the table right now.
        qs = qs.filter(_not_started() | _seated_today())
    elif when == WHEN_PAST:
        qs = qs.exclude(_not_started() | _seated_today())
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(reference__iexact=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )
    if when == WHEN_PAST and not date:
        return qs.order_by("-date", "-time", "-id")
    return qs.order_by("date", "time", "id")


def get_by_reference(reference: str) -> Booking | None:
    return Booking.objects.filter(reference=reference).first()


def today_summary() -> dict:
    today = timezone.localdate()
    agg = Booking.objects.filter(date=today, status__in=ACTIVE_STATUSES).aggregate(
        bookings=Count("id"), guests=Sum("party_size")
    )
    # Only requests that can still be confirmed: a pending booking whose time passed can't be.
    pending = Booking.objects.filter(_not_started(), status=Booking.Status.PENDING).count()
    return {"bookings": agg["bookings"], "guests": agg["guests"] or 0, "pending": pending}


def upcoming(limit: int = 50) -> QuerySet[Booking]:
    """Dashboard: tables still to come (and guests seated now), soonest first."""
    return Booking.objects.filter(
        _not_started() | _seated_today(),
        status__in=(Booking.Status.PENDING, Booking.Status.CONFIRMED, Booking.Status.SEATED),
    ).order_by("date", "time")[:limit]


def availability(date: dt.date) -> dict[str, int | None]:
    """Seats still bookable per slot on `date`: "HH:MM" -> seats left (0 = full), or None when
    that time has already passed (or the date is outside the booking window).
    Public: shares only counts, never who booked."""
    now = timezone.localtime()
    if date < now.date() or date > now.date() + dt.timedelta(days=MAX_DAYS_AHEAD):
        return {t.strftime("%H:%M"): None for t in time_slots()}
    taken = dict(
        Booking.objects.filter(date=date, status__in=ACTIVE_STATUSES)
        .values("time")
        .annotate(seats=Sum("party_size"))
        .values_list("time", "seats")
    )
    result = {}
    for t in time_slots():
        passed = date == now.date() and t <= now.time().replace(tzinfo=None)
        left = max(0, SLOT_CAPACITY - (taken.get(t) or 0))
        result[t.strftime("%H:%M")] = None if passed else left
    return result
