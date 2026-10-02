"""
API privada de la PWA: /api/v1/ (§6 de la propuesta).

Reglas:
- Sesión de Django en el mismo origen + CSRF (cookie `taskflow_csrftoken`, cabecera X-CSRFToken).
- Los datos salen siempre de `request.user`: un proyecto o tarjeta ajeno responde 404, no 403, para
  no revelar que existe.
- Cada acción llama a un servicio (`apps/*/servicios.py`); aquí no hay reglas de negocio.
"""

from datetime import date

from django.conf import settings
from django.contrib.auth import (
    authenticate,
    get_user_model,
    login,
    logout,
    update_session_auth_hash,
)
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.proyectos import servicios as sp
from apps.proyectos.models import PERMISOS, Invitacion, Proyecto, TipoTarjeta
from apps.tarjetas import servicios as st
from apps.tarjetas.models import ORDEN_PRIORIDAD, Estatus, Tarjeta

from . import representacion as rep

Usuario = get_user_model()


class SesionConCsrf(SessionAuthentication):
    """Exige CSRF también a anónimos (entrar, registrarse): DRF solo lo hace con sesión."""

    def authenticate(self, request):
        self.enforce_csrf(request)
        return super().authenticate(request)


class LimiteAcceso(AnonRateThrottle):
    scope = "acceso"


# ---------------------------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------------------------


def _proyecto(request, pk) -> Proyecto:
    return get_object_or_404(Proyecto.objects.de_usuario(request.user).distinct(), pk=pk)


def _tarjetas():
    return Tarjeta.objects.select_related("proyecto", "creada_por").prefetch_related(
        "asignados", "tipos"
    )


def _tarjeta(request, pk) -> Tarjeta:
    visibles = _tarjetas().filter(proyecto__miembros__usuario=request.user).distinct()
    return get_object_or_404(visibles, pk=pk)


def _fecha(valor):
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError as e:
        raise ValidationError({"fecha_fin": "Fecha inválida (AAAA-MM-DD)."}) from e


def _ordenar(tarjetas):
    return sorted(
        tarjetas,
        key=lambda t: (ORDEN_PRIORIDAD[t.prioridad], t.fecha_fin or date.max, -t.pk),
    )


def _datos_usuario(request, obligatorio_correo=True):
    nombre = (request.data.get("nombre") or "").strip()
    apellidos = (request.data.get("apellidos") or "").strip()
    password = request.data.get("password") or ""
    errores = {}
    if not nombre:
        errores["nombre"] = ["Escribe tu nombre."]
    correo = ""
    if obligatorio_correo:
        correo = (request.data.get("correo") or "").strip().lower()
        if not correo or "@" not in correo:
            errores["correo"] = ["Escribe un correo válido."]
        elif Usuario.objects.filter(email__iexact=correo).exists():
            errores["correo"] = ["Ya existe una cuenta con ese correo. Entra con ella."]
    try:
        validate_password(password, Usuario(email=correo, nombre=nombre, apellidos=apellidos))
    except ValidationError as e:
        errores["password"] = e.messages
    if errores:
        raise ValidationError(errores)
    return nombre, apellidos, correo, password


# ---------------------------------------------------------------------------------------------
# Acceso
# ---------------------------------------------------------------------------------------------


@api_view(["GET"])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def csrf(request):
    """Primera llamada de la PWA: deja la cookie CSRF y dice si hay sesión (sin un 403 de yo/)."""
    u = request.user if request.user.is_authenticated else None
    return Response(
        {
            "ok": True,
            "registro_abierto": settings.TASKFLOW_REGISTRO_ABIERTO,
            "usuario": rep.usuario(u),
        }
    )


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def entrar(request):
    correo = (request.data.get("correo") or "").strip()
    password = request.data.get("password") or ""
    u = authenticate(request, username=correo, password=password)
    if u is None:
        return Response(
            {"detalle": "Correo o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST
        )
    login(request, u)
    return Response(rep.usuario(u))


@api_view(["POST"])
def salir(request):
    logout(request)
    return Response({"ok": True})


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def registro(request):
    if not settings.TASKFLOW_REGISTRO_ABIERTO:
        return Response({"detalle": "El registro está cerrado. Pide una invitación."}, status=403)
    nombre, apellidos, correo, password = _datos_usuario(request)
    u = Usuario.objects.create_user(correo, password, nombre=nombre, apellidos=apellidos)
    login(request, u, backend="django.contrib.auth.backends.ModelBackend")
    return Response(rep.usuario(u), status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
def yo(request):
    u = request.user
    if request.method == "PATCH":
        nombre = (request.data.get("nombre", u.nombre) or "").strip()
        if not nombre:
            raise ValidationError({"nombre": "Escribe tu nombre."})
        u.nombre = nombre
        u.apellidos = (request.data.get("apellidos", u.apellidos) or "").strip()
        u.save(update_fields=["nombre", "apellidos", "actualizado_en"])
    # Además del nombre completo, los campos por separado para el formulario del perfil.
    return Response({**rep.usuario(u), "nombre_pila": u.nombre, "apellidos": u.apellidos})


@api_view(["POST"])
def cambiar_password(request):
    u = request.user
    if not u.check_password(request.data.get("actual") or ""):
        raise ValidationError({"actual": "La contraseña actual no es correcta."})
    nueva = request.data.get("nueva") or ""
    try:
        validate_password(nueva, u)
    except ValidationError as e:
        raise ValidationError({"nueva": e.messages}) from e
    u.set_password(nueva)
    u.save(update_fields=["password"])
    update_session_auth_hash(request, u)
    return Response({"ok": True})


@api_view(["GET"])
def mis_tarjetas(request):
    """Asignadas a mí, sin finalizar, en proyectos activos de los que soy miembro (§5)."""
    ts = (
        _tarjetas()
        .filter(
            asignados=request.user,
            proyecto__miembros__usuario=request.user,
            proyecto__archivado_en__isnull=True,
        )
        .exclude(estatus=Estatus.FINALIZADA)
        .distinct()
    )
    ordenadas = sorted(ts, key=lambda t: (t.fecha_fin or date.max, ORDEN_PRIORIDAD[t.prioridad]))
    return Response([rep.tarjeta(t) for t in ordenadas])


# ---------------------------------------------------------------------------------------------
# Proyectos
# ---------------------------------------------------------------------------------------------


@api_view(["GET", "POST"])
def proyectos(request):
    if request.method == "POST":
        p = sp.crear_proyecto(request.user, request.data.get("nombre"))
        return Response(rep.proyecto_detalle(p, request.user), status=status.HTTP_201_CREATED)
    qs = Proyecto.objects.de_usuario(request.user).distinct().order_by("archivado_en", "nombre")
    return Response([rep.proyecto_resumen(p, request.user) for p in qs])


@api_view(["GET", "PATCH", "DELETE"])
def proyecto(request, pk):
    p = _proyecto(request, pk)
    if request.method == "PATCH":
        sp.renombrar_proyecto(p, request.user, request.data.get("nombre"))
    elif request.method == "DELETE":
        sp.eliminar_proyecto(p, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(rep.proyecto_detalle(p, request.user))


@api_view(["POST"])
def proyecto_accion(request, pk, accion):
    p = _proyecto(request, pk)
    if accion == "archivar":
        sp.archivar(p, request.user)
    elif accion == "restaurar":
        sp.restaurar(p, request.user)
    elif accion == "salir":
        sp.salir(p, request.user)
        return Response({"ok": True})
    elif accion == "transferir":
        nuevo = get_object_or_404(Usuario, pk=request.data.get("usuario"))
        sp.transferir(p, request.user, nuevo)
    else:
        return Response({"detalle": "Acción desconocida."}, status=status.HTTP_404_NOT_FOUND)
    return Response(rep.proyecto_detalle(p, request.user))


@api_view(["PATCH", "DELETE"])
def miembro(request, pk, usuario_id):
    p = _proyecto(request, pk)
    u = get_object_or_404(Usuario, pk=usuario_id)
    if request.method == "DELETE":
        sp.quitar_miembro(p, request.user, u)
    else:
        cambios = {k: bool(v) for k, v in request.data.items() if k in PERMISOS}
        sp.cambiar_permisos(p, request.user, u, **cambios)
    return Response(rep.proyecto_detalle(p, request.user))


# ---------------------------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def invitar(request, pk):
    p = _proyecto(request, pk)
    sp.invitar(p, request.user, request.data.get("correo"))
    return Response(rep.proyecto_detalle(p, request.user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def invitacion_accion(request, pk, invitacion_id, accion):
    p = _proyecto(request, pk)
    inv = get_object_or_404(Invitacion, pk=invitacion_id, proyecto=p)
    if accion == "reenviar":
        sp.reenviar_invitacion(inv, request.user)
    elif accion == "cancelar":
        sp.cancelar_invitacion(inv, request.user)
    else:
        return Response({"detalle": "Acción desconocida."}, status=status.HTTP_404_NOT_FOUND)
    return Response(rep.proyecto_detalle(p, request.user))


def _invitacion_por_token(token) -> Invitacion:
    return get_object_or_404(
        Invitacion.objects.select_related("proyecto", "invitada_por"), token=token
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def invitacion_publica(request, token):
    """Lo que ve quien abre el enlace del correo, con o sin sesión."""
    inv = _invitacion_por_token(token)
    return Response(
        {
            "proyecto": inv.proyecto.nombre,
            "correo": inv.correo,
            "invitada_por": rep.usuario(inv.invitada_por)["nombre"] if inv.invitada_por else None,
            "estado": inv.estado,
            "existe_cuenta": Usuario.objects.filter(email__iexact=inv.correo).exists(),
        }
    )


@api_view(["POST"])
def aceptar_invitacion(request, token):
    m = sp.aceptar_invitacion(token, request.user)
    return Response({"proyecto": m.proyecto_id})


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def registro_por_invitacion(request, token):
    """Crea la cuenta con el correo invitado y acepta la invitación en un solo paso."""
    inv = _invitacion_por_token(token)
    if inv.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("La invitación ya se usó o fue cancelada.")
    if Usuario.objects.filter(email__iexact=inv.correo).exists():
        raise ValidationError("Ya existe una cuenta con ese correo: entra con ella para aceptar.")
    nombre, apellidos, _, password = _datos_usuario(request, obligatorio_correo=False)
    with transaction.atomic():
        u = Usuario.objects.create_user(inv.correo, password, nombre=nombre, apellidos=apellidos)
        m = sp.aceptar_invitacion(token, u)
    login(request, u, backend="django.contrib.auth.backends.ModelBackend")
    return Response(
        {"proyecto": m.proyecto_id, "usuario": rep.usuario(u)}, status=status.HTTP_201_CREATED
    )


# ---------------------------------------------------------------------------------------------
# Tipos de tarjeta
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def tipos(request, pk):
    p = _proyecto(request, pk)
    t = sp.crear_tipo(
        p,
        request.user,
        nombre=request.data.get("nombre"),
        color=request.data.get("color"),
        descripcion=request.data.get("descripcion") or "",
    )
    return Response(rep.tipo(t, 0), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
def tipo(request, pk, tipo_id):
    p = _proyecto(request, pk)
    t = get_object_or_404(TipoTarjeta, pk=tipo_id, proyecto=p)
    if request.method == "DELETE":
        sp.eliminar_tipo(t, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    campos = {k: request.data[k] for k in ("nombre", "color", "descripcion") if k in request.data}
    sp.editar_tipo(t, request.user, **campos)
    return Response(rep.tipo(t, t.tarjetas.count()))


# ---------------------------------------------------------------------------------------------
# Tarjetas
# ---------------------------------------------------------------------------------------------


@api_view(["GET", "POST"])
def tarjetas(request, pk):
    p = _proyecto(request, pk)
    if request.method == "POST":
        d = request.data
        t = st.crear_tarjeta(
            p,
            request.user,
            titulo=d.get("titulo"),
            descripcion=d.get("descripcion"),
            prioridad=d.get("prioridad") or "media",
            fecha_fin=_fecha(d.get("fecha_fin")),
            asignados=d.get("asignados") or [],
            tipos=d.get("tipos") or [],
        )
        return Response(
            rep.tarjeta(_tarjeta(request, t.pk), con_historial=True), status=status.HTTP_201_CREATED
        )
    return Response([rep.tarjeta(t) for t in _ordenar(_tarjetas().filter(proyecto=p))])


@api_view(["GET", "PATCH", "DELETE"])
def tarjeta(request, pk):
    t = _tarjeta(request, pk)
    if request.method == "DELETE":
        st.eliminar_tarjeta(t, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == "PATCH":
        campos = {k: request.data[k] for k in st.CAMPOS_EDITABLES if k in request.data}
        if "fecha_fin" in campos:
            campos["fecha_fin"] = _fecha(campos["fecha_fin"])
        st.editar_tarjeta(t, request.user, **campos)
        t = _tarjeta(request, pk)
    return Response(rep.tarjeta(t, con_historial=True))


@api_view(["POST"])
def tarjeta_estatus(request, pk):
    t = _tarjeta(request, pk)
    st.cambiar_estatus(t, request.user, request.data.get("estatus"))
    return Response(rep.tarjeta(_tarjeta(request, pk), con_historial=True))
