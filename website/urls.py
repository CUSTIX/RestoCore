from django.urls import path

from website import views

app_name = "website"

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("menu/", views.MenuView.as_view(), name="menu"),
]
