import datetime as dt

from django.utils import timezone

from bookings import selectors as bookings

CLOSING_TIME = dt.time(22, 0)


def is_open(now: dt.time) -> bool:
    """Open from opening time up to, not including, closing time. Takes the time as an argument
    so the boundaries can be tested without waiting for the clock."""
    opening, _ = bookings.opening_hours()
    return opening <= now < CLOSING_TIME


def cafe_status(request):
    """Opening hours and a live open/closed flag for the public header and footer."""
    opening, last_seating = bookings.opening_hours()
    return {
        "cafe_opening": opening,
        "cafe_last_seating": last_seating,
        "cafe_closing": CLOSING_TIME,
        "cafe_open_now": is_open(timezone.localtime().time()),
    }
