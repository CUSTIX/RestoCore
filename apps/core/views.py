from django.http import JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def healthz(request):
    """Return process health without depending on external services."""

    return JsonResponse({"status": "ok", "service": "restocore"})
