from django.conf import settings


class SecurityHeadersMiddleware:
    """Headers Django doesn't set on its own (it already sends X-Frame-Options, nosniff,
    Referrer-Policy and Cross-Origin-Opener-Policy via SecurityMiddleware/XFrameOptionsMiddleware):

    - Content-Security-Policy: what the browser may load or run. Inline JavaScript is forbidden,
      so an injected <script> or onclick=... cannot run even if escaping ever failed.
    - Permissions-Policy: switch off browser features the app never uses (camera, mic, ...).
    - Cross-Origin-Resource-Policy: other sites can't embed our responses.
    - Cache-Control for signed-in pages: staff screens are never stored by the browser or a proxy,
      so "Back" after logging out on a shared POS terminal shows nothing.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if settings.CONTENT_SECURITY_POLICY:
            response.headers.setdefault("Content-Security-Policy", settings.CONTENT_SECURITY_POLICY)
        response.headers.setdefault("Permissions-Policy", settings.PERMISSIONS_POLICY)
        response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            response.headers["Cache-Control"] = "no-store, private"
        return response
