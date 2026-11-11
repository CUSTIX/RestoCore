import datetime as dt

from django.utils import timezone
from django.views.generic import TemplateView

from bookings import selectors as bookings
from sales import selectors as sales

CLOSING_TIME = dt.time(22, 0)
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _hours_context() -> dict:
    opening, last_seating = bookings.opening_hours()
    now = timezone.localtime()
    return {
        "opening": opening,
        "last_seating": last_seating,
        "closing": CLOSING_TIME,
        "open_now": opening <= now.time() < CLOSING_TIME,
        "week": [{"day": d, "is_today": i == now.weekday()} for i, d in enumerate(WEEKDAYS)],
    }


class HomeView(TemplateView):
    template_name = "website/home.html"

    def get_context_data(self, **kwargs):
        signature = sales.signature_dishes(limit=8)
        return {
            **super().get_context_data(**kwargs),
            **_hours_context(),
            "signature": signature,
            "featured": signature,
        }


class MenuView(TemplateView):
    template_name = "website/menu.html"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            **_hours_context(),
            "categories": sales.public_menu(),
        }
