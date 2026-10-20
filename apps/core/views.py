from django.conf import settings
from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render


def healthz(request):
    """Liveness/readiness para Docker."""
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "error", "database": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})


def portada(request):
    """
    Qué es TaskFlow y cómo instalar la app (§5.1, maqueta instalacion-v2.html). Con la sesión
    abierta manda directo a la app (2026-10-20), salvo con `?portada=1` (Perfil → «Instalar la
    app», que viene a ver los pasos).
    """
    if request.user.is_authenticated and "portada" not in request.GET:
        return redirect("pwa")
    return render(
        request, "core/portada.html", {"registro_abierto": settings.TASKFLOW_REGISTRO_ABIERTO}
    )


def pwa(request):
    """
    /app/: normalmente lo sirve WhiteNoise desde pwa/app/. Esta vista solo responde si la PWA
    no está compilada (desarrollo recién clonado), con la instrucción para compilarla.
    """
    indice = settings.PWA_DIR / "app" / "index.html"
    if indice.exists():
        return HttpResponse(indice.read_bytes(), content_type="text/html; charset=utf-8")
    return HttpResponse(
        "La PWA no está compilada. Ejecuta: "
        'docker compose run --rm frontend sh -c "npm ci && npm run build"',
        content_type="text/plain; charset=utf-8",
        status=503,
    )
