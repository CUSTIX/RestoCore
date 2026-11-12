from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth.forms import AuthenticationForm

from accounts import services
from core import throttle

LOCKED_MESSAGE = "Too many failed sign-in attempts. Please wait 15 minutes and try again."


class ThrottledLoginMixin:
    """Brute-force throttling for any Django login form (accounts.services)."""

    def clean(self):
        username = self.cleaned_data.get("username", "")
        ip = throttle.client_ip(self.request) if self.request else None
        # Check before the password is even tried, so a locked pair learns nothing new.
        if services.is_login_locked(username, ip):
            raise forms.ValidationError(LOCKED_MESSAGE, code="locked")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            services.record_login_failure(username, ip)
            raise
        services.clear_login_failures(username, ip)
        return cleaned


class ThrottledLoginForm(ThrottledLoginMixin, AuthenticationForm):
    """The staff sign-in form."""


class ThrottledAdminLoginForm(ThrottledLoginMixin, AdminAuthenticationForm):
    """Django admin has its own login page; without this it would skip the throttle."""
