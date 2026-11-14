from django.urls import path

from sales import views

app_name = "ordering"

urlpatterns = [
    path("", views.SelfOrderStartView.as_view(), name="start"),
    path("<uuid:token>/", views.SelfOrderStatusView.as_view(), name="status"),
    path("<uuid:token>/cancel/", views.SelfOrderCancelPublicView.as_view(), name="cancel"),
]
