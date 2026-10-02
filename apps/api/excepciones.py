"""
Traduce las excepciones de los servicios a respuestas JSON (§6 de la propuesta).

- `ValidationError` de Django (datos inválidos) → 400 con `{campo: [mensajes]}` o `{"detalle": …}`.
- `PermissionDenied` / `PermisoDenegado` → 403 `{"detalle": …}`.
- `Http404` → 404 `{"detalle": "No encontrado."}`.
"""

from django.core.exceptions import PermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def manejar_excepcion(exc, context):
    if isinstance(exc, DjangoValidationError):
        if hasattr(exc, "error_dict"):
            datos = {
                campo: [m for e in errores for m in e.messages]
                for campo, errores in exc.error_dict.items()
            }
        else:
            datos = {"detalle": " ".join(exc.messages)}
        return Response(datos, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, PermissionDenied):
        mensaje = str(exc) or "No tienes permiso para hacer esto."
        return Response({"detalle": mensaje}, status=status.HTTP_403_FORBIDDEN)
    if isinstance(exc, Http404):
        return Response({"detalle": "No encontrado."}, status=status.HTTP_404_NOT_FOUND)
    respuesta = exception_handler(exc, context)
    if respuesta is not None and isinstance(respuesta.data, dict) and "detail" in respuesta.data:
        respuesta.data = {"detalle": respuesta.data["detail"]}
    return respuesta
