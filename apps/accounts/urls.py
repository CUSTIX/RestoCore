from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "login/",
        LoginView.as_view(
            template_name="accounts/login.html",
            redirect_authenticated_user=True,
        ),
        name="login",
    ),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("account/security/", views.security_settings, name="security"),
    path("account/security/mfa/start/", views.begin_mfa_setup, name="mfa_begin"),
    path("account/security/mfa/setup/", views.mfa_setup, name="mfa_setup"),
    path("account/security/recovery-codes/", views.recovery_codes, name="recovery_codes"),
    path("account/security/recovery-codes/rotate/", views.rotate_codes, name="rotate_codes"),
]
