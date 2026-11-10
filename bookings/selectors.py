import datetime as dt

from django.db.models import Count, Q, QuerySet, Sum
from django.utils import timezone

from bookings.models import Booking
from bookings.services import ACTIVE_STATUSES, LAST_SEATING, OPENING_TIME


def opening_hours() -> tuple[dt.time, dt.time]:
    return OPENING_TIME, LAST_SEATING


def filter_bookings(*, date=None, status: str = "", q: str = "") -> QuerySet[Booking]:
    qs = Booking.objects.all()
    if date:
        qs = qs.filter(date=date)
    if status:
        qs = qs.filter(status=status)
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(reference__iexact=q)
            | Q(phone__icontains=q)
            | Q(email__icontains=q)
        )
    return qs.order_by("date", "time", "id")


def get_by_reference(reference: str) -> Booking | None:
    return Booking.objects.filter(reference=reference).first()


def today_summary() -> dict:
    today = timezone.localdate()
    agg = Booking.objects.filter(date=today, status__in=ACTIVE_STATUSES).aggregate(
        bookings=Count("id"), guests=Sum("party_size")
    )
    pending = Booking.objects.filter(status=Booking.Status.PENDING, date__gte=today).count()
    return {"bookings": agg["bookings"], "guests": agg["guests"] or 0, "pending": pending}


def upcoming(limit: int = 50) -> QuerySet[Booking]:
    today = timezone.localdate()
    return Booking.objects.filter(date__gte=today, status__in=ACTIVE_STATUSES).order_by(
        "date", "time"
    )[:limit]
