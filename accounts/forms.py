from django import forms
from django.contrib.auth.forms import AuthenticationForm

from accounts import services

LOCKED_MESSAGE = "Too many failed sign-in attempts. Please wait 15 minutes and try again."


class ThrottledLoginForm(AuthenticationForm):
    """Django's login form plus brute-force throttling (accounts.services)."""

    error_messages = {**AuthenticationForm.error_messages, "locked": LOCKED_MESSAGE}

    def clean(self):
        username = self.cleaned_data.get("username", "")
        ip = services.client_ip(self.request) if self.request else None
        # Check before the password is even tried, so a locked pair learns nothing new.
        if services.is_login_locked(username, ip):
            raise forms.ValidationError(self.error_messages["locked"], code="locked")
        try:
            cleaned = super().clean()
        except forms.ValidationError:
            services.record_login_failure(username, ip)
            raise
        services.clear_login_failures(username, ip)
        return cleaned
