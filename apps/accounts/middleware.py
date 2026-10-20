from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import resolve, reverse

from .mfa import get_confirmed_totp_device
from .security import is_mfa_verified, requires_mfa

EXEMPT_URL_NAMES = {
    "accounts:login",
    "accounts:logout",
    "accounts:security",
    "accounts:mfa_begin",
    "accounts:mfa_setup",
    "accounts:mfa_challenge",
    "accounts:recovery_codes",
    "accounts:rotate_codes",
    "core:healthz",
}
INTERNAL_NAMESPACES = {
    "admin",
    "bookings",
    "core",
    "inventory",
    "orders",
    "payroll",
    "pos",
    "reports",
    "staff",
}


class MFAEnforcementMiddleware:
    """Require MFA for policy-bound accounts before internal application access."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if not user.is_authenticated or not requires_mfa(user) or is_mfa_verified(user):
            return self.get_response(request)

        match = resolve(request.path_info)
        url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        if url_name in EXEMPT_URL_NAMES:
            return self.get_response(request)

        if match.namespace not in INTERNAL_NAMESPACES:
            return self.get_response(request)

        if get_confirmed_totp_device(user) is None:
            return redirect("accounts:security")

        challenge_url = reverse("accounts:mfa_challenge")
        query = urlencode({"next": request.get_full_path()})
        return redirect(f"{challenge_url}?{query}")
