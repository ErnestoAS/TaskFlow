"""
API privada de la PWA: /api/v1/ (§6 de la propuesta).

Reglas:
- Sesión de Django en el mismo origen + CSRF (cookie `taskflow_csrftoken`, cabecera X-CSRFToken).
- Los datos salen siempre de `request.user`: una pizarra, lista, actividad o elemento ajeno responde
  404, no 403, para no revelar que existe.
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
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    parser_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle

from apps.actividades import servicios as st
from apps.actividades.almacen import TIPOS_EN_LINEA
from apps.actividades.models import Actividad, Adjunto, ElementoChecklist
from apps.pizarras import servicios as sp
from apps.pizarras.models import (
    PERMISOS,
    Invitacion,
    Lista,
    Pizarra,
    Solicitante,
    TipoActividad,
)
from apps.usuarios import servicios as su
from apps.usuarios.models import CodigoCorreo

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


def _pizarra(request, pk) -> Pizarra:
    return get_object_or_404(Pizarra.objects.de_usuario(request.user).distinct(), pk=pk)


def _actividades():
    return Actividad.objects.select_related(
        "pizarra",
        "lista",
        "creada_por",
        "elemento_origen__actividad",
        "solicitada_por",
        "solicitante_externo",
    ).prefetch_related(
        "asignados",
        "tipos",
        "checklist__actividad_creada__lista",
        "adjuntos__subido_por",
    )


def _actividad(request, pk) -> Actividad:
    visibles = _actividades().filter(pizarra__miembros__usuario=request.user).distinct()
    return get_object_or_404(visibles, pk=pk)


def _lista(request, pk) -> Lista:
    visibles = Lista.objects.select_related("pizarra").filter(
        pizarra__miembros__usuario=request.user
    )
    return get_object_or_404(visibles.distinct(), pk=pk)


def _elemento(request, pk) -> ElementoChecklist:
    visibles = ElementoChecklist.objects.select_related("actividad__pizarra").filter(
        actividad__pizarra__miembros__usuario=request.user
    )
    return get_object_or_404(visibles.distinct(), pk=pk)


def _fecha(valor, campo="fecha_fin"):
    if valor in (None, ""):
        return None
    try:
        return date.fromisoformat(str(valor))
    except ValueError as e:
        raise ValidationError({campo: "Fecha inválida (AAAA-MM-DD)."}) from e


def _datos_actividad(d) -> dict:
    """Campos de alta de actividad presentes en la petición, ya convertidos."""
    datos = {
        k: d[k]
        for k in ("titulo", "descripcion", "lista", "lista_al_completar", *st.CAMPOS_SOLICITANTE)
        if k in d
    }
    datos["asignados"] = d.get("asignados") or []
    datos["tipos"] = d.get("tipos") or []
    datos["fecha_solicitud"] = _fecha(d.get("fecha_solicitud"), "fecha_solicitud")
    datos["fecha_fin"] = _fecha(d.get("fecha_fin"))
    datos["checklist"] = [str(t) for t in d.get("checklist") or []]
    datos["arriba"] = bool(d.get("arriba"))
    return datos


def _detalle(request, pk):
    return Response(rep.actividad(_actividad(request, pk), con_detalle=True))


def _nombre(request, actual=None) -> dict:
    """Nombre y apellidos de la petición; el primer apellido es obligatorio (§4.3)."""
    actual = actual or {}
    datos = {
        campo: (request.data.get(campo, actual.get(campo, "")) or "").strip()
        for campo in ("nombre", "primer_apellido", "segundo_apellido")
    }
    errores = {}
    if not datos["nombre"]:
        errores["nombre"] = ["Escribe tu nombre."]
    if not datos["primer_apellido"]:
        errores["primer_apellido"] = ["Escribe tu primer apellido."]
    if errores:
        raise ValidationError(errores)
    return datos


def _datos_usuario(request, obligatorio_correo=True):
    errores = {}
    try:
        nombre = _nombre(request)
    except ValidationError as e:
        nombre = {}
        errores.update(e.message_dict)
    password = request.data.get("password") or ""
    correo = ""
    if obligatorio_correo:
        correo = (request.data.get("correo") or "").strip().lower()
        if not correo or "@" not in correo:
            errores["correo"] = ["Escribe un correo válido."]
        elif Usuario.objects.filter(email__iexact=correo).exists():
            errores["correo"] = ["Ya existe una cuenta con ese correo. Entra con ella."]
    try:
        validate_password(password, Usuario(email=correo, **nombre))
    except ValidationError as e:
        errores["password"] = e.messages
    if errores:
        raise ValidationError(errores)
    return nombre, correo, password


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


def _por_verificar(u):
    """Respuesta para una cuenta que aún no confirma su correo: la PWA pasa a capturar el código."""
    return Response(
        {
            "detalle": f"Confirma tu correo: te enviamos un código a {u.email}.",
            "verificar": True,
            "correo": u.email,
        },
        status=status.HTTP_403_FORBIDDEN,
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
    if not u.correo_verificado:
        try:
            su.enviar_codigo(u, CodigoCorreo.Proposito.VERIFICAR)
        except ValidationError:
            pass  # Se mandó uno hace poco: sigue valiendo ese.
        return _por_verificar(u)
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
    """Crea la cuenta sin sesión y manda el código; se entra al confirmarlo (auth/verificar/)."""
    if not settings.TASKFLOW_REGISTRO_ABIERTO:
        return Response({"detalle": "El registro está cerrado. Pide una invitación."}, status=403)
    nombre, correo, password = _datos_usuario(request)
    with transaction.atomic():
        u = Usuario.objects.create_user(correo, password, **nombre)
        su.enviar_codigo(u, CodigoCorreo.Proposito.VERIFICAR)
    return Response({"verificar": True, "correo": u.email}, status=status.HTTP_201_CREATED)


def _entrar_con(request, u):
    login(request, u, backend="django.contrib.auth.backends.ModelBackend")
    return Response(rep.usuario(u))


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def verificar(request):
    u = su.verificar_correo(request.data.get("correo"), request.data.get("codigo"))
    return _entrar_con(request, u)


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def reenviar_verificacion(request):
    su.pedir_verificacion(request.data.get("correo"))
    return Response({"ok": True})


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def recuperar(request):
    """Responde igual exista o no la cuenta, para no revelar qué correos están registrados."""
    su.pedir_recuperacion(request.data.get("correo"))
    return Response({"ok": True})


@api_view(["POST"])
@authentication_classes([SesionConCsrf])
@permission_classes([AllowAny])
@throttle_classes([LimiteAcceso])
def recuperar_confirmar(request):
    d = request.data
    u = su.restablecer_password(d.get("correo"), d.get("codigo"), d.get("password") or "")
    return _entrar_con(request, u)


@api_view(["GET", "PATCH"])
def yo(request):
    u = request.user
    campos = ("nombre", "primer_apellido", "segundo_apellido")
    if request.method == "PATCH":
        datos = _nombre(request, actual={c: getattr(u, c) for c in campos})
        for campo, valor in datos.items():
            setattr(u, campo, valor)
        u.save(update_fields=[*campos, "actualizado_en"])
    # Además del nombre completo, los campos por separado para el formulario del perfil.
    return Response(
        {
            **rep.usuario(u),
            "nombre_pila": u.nombre,
            "primer_apellido": u.primer_apellido,
            "segundo_apellido": u.segundo_apellido,
        }
    )


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
def mis_actividades(request):
    """Asignadas a mí en pizarras activas de las que soy miembro."""
    ts = (
        _actividades()
        .filter(
            asignados=request.user,
            pizarra__miembros__usuario=request.user,
            pizarra__archivada_en__isnull=True,
        )
        .distinct()
    )
    ordenadas = sorted(ts, key=lambda t: (t.fecha_fin or date.max, t.creado_en))
    return Response([rep.actividad(t) for t in ordenadas])


# ---------------------------------------------------------------------------------------------
# Pizarras
# ---------------------------------------------------------------------------------------------


@api_view(["GET", "POST"])
def pizarras(request):
    if request.method == "POST":
        p = sp.crear_pizarra(request.user, request.data.get("nombre"))
        return Response(rep.pizarra_detalle(p, request.user), status=status.HTTP_201_CREATED)
    qs = Pizarra.objects.de_usuario(request.user).distinct().order_by("archivada_en", "nombre")
    return Response([rep.pizarra_resumen(p, request.user) for p in qs])


@api_view(["GET", "PATCH", "DELETE"])
def pizarra(request, pk):
    p = _pizarra(request, pk)
    if request.method == "PATCH":
        sp.renombrar_pizarra(p, request.user, request.data.get("nombre"))
    elif request.method == "DELETE":
        sp.eliminar_pizarra(p, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(rep.pizarra_detalle(p, request.user))


@api_view(["POST"])
def pizarra_accion(request, pk, accion):
    p = _pizarra(request, pk)
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
    return Response(rep.pizarra_detalle(p, request.user))


@api_view(["PATCH", "DELETE"])
def miembro(request, pk, usuario_id):
    p = _pizarra(request, pk)
    u = get_object_or_404(Usuario, pk=usuario_id)
    if request.method == "DELETE":
        sp.quitar_miembro(p, request.user, u)
    else:
        cambios = {k: bool(v) for k, v in request.data.items() if k in PERMISOS}
        sp.cambiar_permisos(p, request.user, u, **cambios)
    return Response(rep.pizarra_detalle(p, request.user))


# ---------------------------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def invitar(request, pk):
    p = _pizarra(request, pk)
    sp.invitar(p, request.user, request.data.get("correo"))
    return Response(rep.pizarra_detalle(p, request.user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def invitacion_accion(request, pk, invitacion_id, accion):
    p = _pizarra(request, pk)
    inv = get_object_or_404(Invitacion, pk=invitacion_id, pizarra=p)
    if accion == "reenviar":
        sp.reenviar_invitacion(inv, request.user)
    elif accion == "cancelar":
        sp.cancelar_invitacion(inv, request.user)
    else:
        return Response({"detalle": "Acción desconocida."}, status=status.HTTP_404_NOT_FOUND)
    return Response(rep.pizarra_detalle(p, request.user))


def _invitacion_por_token(token) -> Invitacion:
    return get_object_or_404(
        Invitacion.objects.select_related("pizarra", "invitada_por"), token=token
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def invitacion_publica(request, token):
    """Lo que ve quien abre el enlace del correo, con o sin sesión."""
    inv = _invitacion_por_token(token)
    return Response(
        {
            "pizarra": inv.pizarra.nombre,
            "correo": inv.correo,
            "invitada_por": rep.usuario(inv.invitada_por)["nombre"] if inv.invitada_por else None,
            "estado": inv.estado,
            "existe_cuenta": Usuario.objects.filter(email__iexact=inv.correo).exists(),
        }
    )


@api_view(["POST"])
def aceptar_invitacion(request, token):
    m = sp.aceptar_invitacion(token, request.user)
    return Response({"pizarra": m.pizarra_id})


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
    nombre, _, password = _datos_usuario(request, obligatorio_correo=False)
    with transaction.atomic():
        # El enlace llegó a ese correo: queda verificado sin pedir código (§7).
        u = Usuario.objects.create_user(
            inv.correo, password, correo_verificado_en=timezone.now(), **nombre
        )
        m = sp.aceptar_invitacion(token, u)
    login(request, u, backend="django.contrib.auth.backends.ModelBackend")
    return Response(
        {"pizarra": m.pizarra_id, "usuario": rep.usuario(u)}, status=status.HTTP_201_CREATED
    )


# ---------------------------------------------------------------------------------------------
# Listas (§4.6). Cada acción devuelve la pizarra completa: el tablero se vuelve a pintar con ella.
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def listas(request, pk):
    p = _pizarra(request, pk)
    sp.crear_lista(p, request.user, request.data.get("nombre"))
    return Response(rep.pizarra_detalle(p, request.user), status=status.HTTP_201_CREATED)


@api_view(["POST"])
def listas_orden(request, pk):
    p = _pizarra(request, pk)
    sp.ordenar_listas(p, request.user, request.data.get("ids"))
    return Response(rep.pizarra_detalle(p, request.user))


@api_view(["PATCH", "DELETE"])
def lista(request, pk):
    lst = _lista(request, pk)
    if request.method == "DELETE":
        sp.eliminar_lista(lst, request.user)
    else:
        campos = {k: request.data[k] for k in ("nombre",) if k in request.data}
        sp.editar_lista(lst, request.user, **campos)
    return Response(rep.pizarra_detalle(lst.pizarra, request.user))


# ---------------------------------------------------------------------------------------------
# Tipos de actividad
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def tipos(request, pk):
    p = _pizarra(request, pk)
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
    p = _pizarra(request, pk)
    t = get_object_or_404(TipoActividad, pk=tipo_id, pizarra=p)
    if request.method == "DELETE":
        sp.eliminar_tipo(t, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    campos = {k: request.data[k] for k in ("nombre", "color", "descripcion") if k in request.data}
    sp.editar_tipo(t, request.user, **campos)
    return Response(rep.tipo(t, t.actividades.count()))


# ---------------------------------------------------------------------------------------------
# Solicitantes externos (Etapa 3.8). Devuelven la pizarra, como las listas.
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def solicitantes(request, pk):
    p = _pizarra(request, pk)
    sp.crear_solicitante(p, request.user, request.data.get("nombre"))
    return Response(rep.pizarra_detalle(p, request.user), status=status.HTTP_201_CREATED)


@api_view(["PATCH", "DELETE"])
def solicitante(request, pk):
    visibles = Solicitante.objects.select_related("pizarra").filter(
        pizarra__miembros__usuario=request.user
    )
    s = get_object_or_404(visibles.distinct(), pk=pk)
    if request.method == "DELETE":
        sp.eliminar_solicitante(s, request.user)
    else:
        sp.renombrar_solicitante(s, request.user, request.data.get("nombre"))
    return Response(rep.pizarra_detalle(s.pizarra, request.user))


# ---------------------------------------------------------------------------------------------
# Actividades
# ---------------------------------------------------------------------------------------------


@api_view(["GET", "POST"])
def actividades(request, pk):
    p = _pizarra(request, pk)
    if request.method == "POST":
        t = st.crear_actividad(p, request.user, **_datos_actividad(request.data))
        return Response(
            rep.actividad(_actividad(request, t.pk), con_detalle=True),
            status=status.HTTP_201_CREATED,
        )
    ts = _actividades().filter(pizarra=p).order_by("lista__posicion", "posicion", "id")
    return Response([rep.actividad(t) for t in ts])


@api_view(["GET", "PATCH", "DELETE"])
def actividad(request, pk):
    t = _actividad(request, pk)
    if request.method == "DELETE":
        st.eliminar_actividad(t, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
    if request.method == "PATCH":
        campos = {k: request.data[k] for k in st.CAMPOS_EDITABLES if k in request.data}
        for campo in ("fecha_solicitud", "fecha_fin"):
            if campo in campos:
                campos[campo] = _fecha(campos[campo], campo)
        st.editar_actividad(t, request.user, **campos)
    return _detalle(request, pk)


@api_view(["POST"])
def actividad_mover(request, pk):
    """Arrastrar o «Mover a»: `{lista, posicion}`; sin posición, al final de la lista."""
    t = _actividad(request, pk)
    st.mover_actividad(t, request.user, request.data.get("lista"), request.data.get("posicion"))
    return _detalle(request, pk)


# ---------------------------------------------------------------------------------------------
# Adjuntos (Etapa 3.8, §4.4 y §7)
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
@parser_classes([MultiPartParser])
def adjuntos(request, pk):
    """Multipart, campo `archivo`. Devuelve la actividad."""
    t = _actividad(request, pk)
    st.adjuntar(t, request.user, request.FILES.get("archivo"))
    return Response(rep.actividad(_actividad(request, pk), con_detalle=True), status=201)


@api_view(["GET", "DELETE"])
def adjunto(request, pk):
    """
    Descarga, solo para miembros (lo ajeno es 404). Imágenes y PDF se muestran en el navegador; lo
    demás (también SVG y HTML) se descarga, y nada se interpreta como otro tipo (`nosniff`) ni
    puede ejecutar código en el dominio de TaskFlow (`sandbox`).
    """
    visibles = Adjunto.objects.select_related("actividad__pizarra").filter(
        actividad__pizarra__miembros__usuario=request.user
    )
    a = get_object_or_404(visibles.distinct(), pk=pk)
    if request.method == "DELETE":
        st.quitar_adjunto(a, request.user)
        return _detalle(request, a.actividad_id)
    en_linea = a.tipo in TIPOS_EN_LINEA
    respuesta = FileResponse(
        a.archivo.open("rb"),
        as_attachment=not en_linea,
        filename=a.nombre,
        content_type=a.tipo if en_linea else "application/octet-stream",
    )
    respuesta["X-Content-Type-Options"] = "nosniff"
    respuesta["Content-Security-Policy"] = "sandbox"
    respuesta["Cache-Control"] = "private, max-age=3600"
    return respuesta


# ---------------------------------------------------------------------------------------------
# Checklist (§4.6). Cada acción devuelve la actividad completa a la que pertenece el elemento.
# ---------------------------------------------------------------------------------------------


@api_view(["POST"])
def checklist(request, pk):
    t = _actividad(request, pk)
    st.agregar_elemento(t, request.user, request.data.get("texto"))
    return Response(rep.actividad(_actividad(request, pk), con_detalle=True), status=201)


@api_view(["POST"])
def checklist_orden(request, pk):
    t = _actividad(request, pk)
    st.ordenar_checklist(t, request.user, request.data.get("ids"))
    return _detalle(request, pk)


@api_view(["PATCH", "DELETE"])
def elemento(request, pk):
    e = _elemento(request, pk)
    if request.method == "DELETE":
        st.quitar_elemento(e, request.user)
    else:
        campos = {k: request.data[k] for k in ("texto", "hecho") if k in request.data}
        st.editar_elemento(e, request.user, **campos)
    return _detalle(request, e.actividad_id)


@api_view(["POST"])
def elemento_convertir(request, pk):
    """Crea la actividad enlazada. Devuelve la actividad original y la nueva."""
    e = _elemento(request, pk)
    nueva = st.convertir_elemento(e, request.user, **_datos_actividad(request.data))
    return Response(
        {
            "actividad": rep.actividad(_actividad(request, e.actividad_id), con_detalle=True),
            "nueva": rep.actividad(_actividad(request, nueva.pk), con_detalle=True),
        },
        status=status.HTTP_201_CREATED,
    )
