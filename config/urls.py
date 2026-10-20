"""Root URL configuration for RestoCore."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("manage/system/", admin.site.urls),
    path("", include("apps.website.urls")),
    path("", include("apps.core.urls")),
]
