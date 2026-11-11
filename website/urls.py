from django.urls import path
from django.views.generic import RedirectView

from website import views

app_name = "website"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("menu/", views.MenuView.as_view(), name="menu"),
    path("favicon.svg", views.FaviconView.as_view(), name="favicon"),
    # Browsers ask for /favicon.ico on their own; point them at the SVG instead of a 404.
    path("favicon.ico", RedirectView.as_view(pattern_name="website:favicon", permanent=True)),
]
