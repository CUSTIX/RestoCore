from django.views.generic import TemplateView

from bookings import selectors as bookings
from sales import selectors as sales


class HomeView(TemplateView):
    template_name = "website/home.html"

    def get_context_data(self, **kwargs):
        opening, last = bookings.opening_hours()
        featured = [item for cat in sales.public_menu() for item in cat.shown][:6]
        return {
            **super().get_context_data(**kwargs),
            "opening": opening,
            "last_seating": last,
            "featured": featured,
        }


class MenuView(TemplateView):
    template_name = "website/menu.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "categories": sales.public_menu()}
