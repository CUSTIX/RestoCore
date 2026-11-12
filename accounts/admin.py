from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from accounts.models import LoginFailure, User

admin.site.register(User, UserAdmin)


@admin.register(LoginFailure)
class LoginFailureAdmin(admin.ModelAdmin):
    """Read-only audit view of failed sign-ins."""

    list_display = ("username", "ip_address", "created_at")
    list_filter = ("created_at",)
    search_fields = ("username", "ip_address")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
