from django.urls import path

from .views import WorkspaceView, healthz

app_name = "core"

urlpatterns = [
    path("healthz/", healthz, name="healthz"),
    path("workspace/", WorkspaceView.as_view(), name="workspace"),
]
