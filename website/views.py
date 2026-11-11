from django.utils import timezone
from django.views.generic import TemplateView

from sales import selectors as sales
from website.context_processors import cafe_status

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _week() -> list[dict]:
    today = timezone.localtime().weekday()
    return [{"day": d, "is_today": i == today} for i, d in enumerate(WEEKDAYS)]


class HomeView(TemplateView):
    template_name = "website/home.html"

    def get_context_data(self, **kwargs):
        status = cafe_status(self.request)
        return {
            **super().get_context_data(**kwargs),
            # kept for templates/tests that use the shorter names
            "opening": status["cafe_opening"],
            "last_seating": status["cafe_last_seating"],
            "closing": status["cafe_closing"],
            "open_now": status["cafe_open_now"],
            "week": _week(),
            "signature": sales.signature_dishes(limit=6),
        }


class FaviconView(TemplateView):
    """Tab icon rendered from a template, so local branding (local/templates) can override it."""

    template_name = "brand/favicon.svg"
    content_type = "image/svg+xml"

    def get(self, request, *args, **kwargs):
        response = super().get(request, *args, **kwargs)
        response["Cache-Control"] = "public, max-age=86400"
        return response


class MenuView(TemplateView):
    template_name = "website/menu.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "categories": sales.public_menu()}
