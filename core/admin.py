from django.contrib import admin

from core.models import ThrottleEvent


@admin.register(ThrottleEvent)
class ThrottleEventAdmin(admin.ModelAdmin):
    """Read-only audit view of rate-limited events (failed sign-ins, public bookings)."""

    list_display = ("scope", "key", "created_at")
    list_filter = ("scope", "created_at")
    search_fields = ("key",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
