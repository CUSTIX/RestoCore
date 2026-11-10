from django.db import connection
from django.http import HttpResponse


def healthz(request):
    """Liveness check used by Docker/CI/deploy: proves the app runs and the DB answers."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")
