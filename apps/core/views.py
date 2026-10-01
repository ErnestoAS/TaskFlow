from django.db import connection
from django.http import JsonResponse


def healthz(request):
    """Liveness/readiness para Docker."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
