from django.db import connection
from django.http import HttpResponse


def healthz(request):
    """Liveness check used by Docker/CI/deploy: proves the app runs and the DB answers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


def livez(request):
    """Keep-awake ping: proves the web process answers, without touching the database.

    The uptime heartbeat hits this every few minutes. Skipping the DB lets the free Neon
    database still suspend when nobody uses the app, so its free compute hours are not spent.
    """
    return HttpResponse("ok", content_type="text/plain")
