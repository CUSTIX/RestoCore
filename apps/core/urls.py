from django.urls import path

from .views import healthz

app_name = "core"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
]
