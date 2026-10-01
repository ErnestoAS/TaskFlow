from .views import healthz

HEALTHCHECK_PATH = "/healthz/"


class HealthCheckMiddleware:
    """
    Responde /healthz/ antes de validar ALLOWED_HOSTS o redirigir a HTTPS, para que
    los healthchecks internos de Docker (Host: 127.0.0.1) funcionen en producción.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # path_info y no path: con FORCE_SCRIPT_NAME, `path` llega como /taskflow/healthz/.
        if request.path_info == HEALTHCHECK_PATH:
            return healthz(request)
        return self.get_response(request)
