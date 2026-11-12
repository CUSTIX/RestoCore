from django.conf import settings
from django.contrib.auth import views as auth_views
from django.shortcuts import render

from accounts.forms import ThrottledLoginForm


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True
    authentication_form = ThrottledLoginForm


class PasswordChangeView(auth_views.PasswordChangeView):
    """Normal password change, switched off on the public demo (DEMO_MODE) so one visitor can't
    lock everyone else out of the shared demo accounts."""

    template_name = "accounts/password_change.html"

    def dispatch(self, request, *args, **kwargs):
        if settings.DEMO_MODE and request.user.is_authenticated:
            return render(request, "accounts/password_change_disabled.html", status=403)
        return super().dispatch(request, *args, **kwargs)
