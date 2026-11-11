import datetime as dt

from django.utils import timezone

from bookings import selectors as bookings

CLOSING_TIME = dt.time(22, 0)


def cafe_status(request):
    """Opening hours and a live open/closed flag for the public header and footer."""
    opening, last_seating = bookings.opening_hours()
    now = timezone.localtime().time()
    return {
        "cafe_opening": opening,
        "cafe_last_seating": last_seating,
        "cafe_closing": CLOSING_TIME,
        "cafe_open_now": opening <= now < CLOSING_TIME,
    }
