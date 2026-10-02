"""
Reglas de negocio de proyectos, miembros, invitaciones y tipos (§4.5 de la propuesta).

Toda acción pasa por aquí: las vistas y la API (cuando existan) solo traducen la petición y
llaman a estas funciones. Así las reglas viven en un solo lugar y se prueban sin HTTP.

- `PermisoDenegado`: el usuario no puede hacer eso (no es miembro, no es dueño, le falta el
  permiso o el proyecto está archivado). La API lo traducirá a 403.
- `ValidationError`: la petición tiene datos inválidos (correo repetido, tipo de otro proyecto…).
  La API lo traducirá a 400.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from .models import PERMISOS, Invitacion, MiembroProyecto, Proyecto, TipoTarjeta

# Tope de reenvíos de una misma invitación: las invitaciones no vencen y se pueden reenviar
# (decidido 2026-10-01); el tope solo evita usar el sistema para mandar correo masivo.
MAX_ENVIOS_INVITACION = 10


class PermisoDenegado(PermissionDenied):
    """El usuario no puede realizar la acción sobre el proyecto."""


# ---------------------------------------------------------------------------------------------
# Consultas de membresía y permisos
# ---------------------------------------------------------------------------------------------


def membresia(proyecto: Proyecto, usuario) -> MiembroProyecto | None:
    if not getattr(usuario, "is_authenticated", False):
        return None
    return MiembroProyecto.objects.filter(proyecto=proyecto, usuario=usuario).first()


def exigir_miembro(proyecto: Proyecto, usuario) -> MiembroProyecto:
    m = membresia(proyecto, usuario)
    if m is None:
        raise PermisoDenegado("No eres miembro de este proyecto.")
    return m


def exigir_activo(proyecto: Proyecto) -> None:
    if proyecto.archivado:
        raise PermisoDenegado("El proyecto está archivado: es de solo lectura.")


def exigir_dueno(proyecto: Proyecto, usuario) -> MiembroProyecto:
    m = exigir_miembro(proyecto, usuario)
    if not m.es_dueno:
        raise PermisoDenegado("Solo el dueño del proyecto puede hacer esto.")
    return m


def exigir_permiso(proyecto: Proyecto, usuario, permiso: str) -> MiembroProyecto:
    """Miembro, proyecto activo y permiso concedido (el dueño siempre lo tiene)."""
    m = exigir_miembro(proyecto, usuario)
    exigir_activo(proyecto)
    if not m.puede(permiso):
        raise PermisoDenegado("El dueño del proyecto no te ha dado permiso para hacer esto.")
    return m


# ---------------------------------------------------------------------------------------------
# Proyectos
# ---------------------------------------------------------------------------------------------


@transaction.atomic
def crear_proyecto(usuario, nombre: str) -> Proyecto:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    proyecto = Proyecto.objects.create(nombre=nombre, creado_por=usuario)
    MiembroProyecto.objects.create(
        proyecto=proyecto, usuario=usuario, rol=MiembroProyecto.Rol.DUENO
    )
    return proyecto


def renombrar_proyecto(proyecto: Proyecto, por, nombre: str) -> Proyecto:
    exigir_dueno(proyecto, por)
    exigir_activo(proyecto)
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    proyecto.nombre = nombre
    proyecto.save(update_fields=["nombre", "actualizado_en"])
    return proyecto


def archivar(proyecto: Proyecto, por) -> Proyecto:
    exigir_dueno(proyecto, por)
    if not proyecto.archivado:
        proyecto.archivado_en = timezone.now()
        proyecto.save(update_fields=["archivado_en", "actualizado_en"])
    return proyecto


def restaurar(proyecto: Proyecto, por) -> Proyecto:
    exigir_dueno(proyecto, por)
    if proyecto.archivado:
        proyecto.archivado_en = None
        proyecto.save(update_fields=["archivado_en", "actualizado_en"])
    return proyecto


def eliminar_proyecto(proyecto: Proyecto, por) -> None:
    """Borra el proyecto con sus tarjetas, tipos, miembros e invitaciones (CASCADE)."""
    exigir_dueno(proyecto, por)
    proyecto.delete()


@transaction.atomic
def transferir(proyecto: Proyecto, por, nuevo_dueno, *, como_administrador: bool = False) -> None:
    """
    Pasa el proyecto a otro miembro. El dueño anterior queda como miembro con todos los permisos.

    `como_administrador=True` es para el admin de Django (dueño con la cuenta desactivada, §4.5):
    entonces `por` debe ser staff y no hace falta que sea el dueño.
    """
    if como_administrador:
        if not getattr(por, "is_staff", False):
            raise PermisoDenegado("Solo un administrador puede transferir un proyecto ajeno.")
    else:
        exigir_dueno(proyecto, por)
    actual = MiembroProyecto.objects.select_for_update().get(
        proyecto=proyecto, rol=MiembroProyecto.Rol.DUENO
    )
    nuevo = (
        MiembroProyecto.objects.select_for_update()
        .filter(proyecto=proyecto, usuario=nuevo_dueno)
        .first()
    )
    if nuevo is None:
        raise ValidationError("Solo se puede transferir a un miembro del proyecto.")
    if nuevo.pk == actual.pk:
        return
    # Orden obligado por la restricción «un solo dueño»: primero bajar, luego subir.
    actual.rol = MiembroProyecto.Rol.MIEMBRO
    for permiso in PERMISOS:
        setattr(actual, f"puede_{permiso}", True)
    actual.save()
    nuevo.rol = MiembroProyecto.Rol.DUENO
    nuevo.save(update_fields=["rol"])


# ---------------------------------------------------------------------------------------------
# Miembros
# ---------------------------------------------------------------------------------------------


def cambiar_permisos(proyecto: Proyecto, por, usuario, **permisos: bool) -> MiembroProyecto:
    """`cambiar_permisos(p, dueno, luis, eliminar=True, gestionar_tipos=False)`."""
    exigir_dueno(proyecto, por)
    exigir_activo(proyecto)
    desconocidos = set(permisos) - set(PERMISOS)
    if desconocidos:
        raise ValidationError(f"Permisos desconocidos: {', '.join(sorted(desconocidos))}.")
    m = exigir_miembro(proyecto, usuario)
    if m.es_dueno:
        raise ValidationError("El dueño siempre tiene todos los permisos.")
    for permiso, valor in permisos.items():
        setattr(m, f"puede_{permiso}", bool(valor))
    m.save()
    return m


def _desasignar(proyecto: Proyecto, usuario) -> None:
    # Import local: tarjetas depende de proyectos, no al revés.
    from apps.tarjetas.models import Tarjeta

    for tarjeta in Tarjeta.objects.filter(proyecto=proyecto, asignados=usuario):
        tarjeta.asignados.remove(usuario)


@transaction.atomic
def quitar_miembro(proyecto: Proyecto, por, usuario) -> None:
    exigir_dueno(proyecto, por)
    exigir_activo(proyecto)
    m = exigir_miembro(proyecto, usuario)
    if m.es_dueno:
        raise ValidationError("No se puede quitar al dueño. Primero transfiere el proyecto.")
    _desasignar(proyecto, usuario)
    m.delete()


@transaction.atomic
def salir(proyecto: Proyecto, usuario) -> None:
    m = exigir_miembro(proyecto, usuario)
    if m.es_dueno:
        raise ValidationError(
            "El dueño no puede salir. Primero transfiere el proyecto a otro miembro."
        )
    _desasignar(proyecto, usuario)
    m.delete()


# ---------------------------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------------------------


def url_invitacion(invitacion: Invitacion) -> str:
    # Ruta de la PWA que acepta la invitación. La PWA usa rutas con # (§5), así que el enlace
    # funciona igual con o sin prefijo. TASKFLOW_URL ya incluye /taskflow.
    return f"{settings.TASKFLOW_URL.rstrip('/')}/app/#/invitacion/{invitacion.token}"


def _enviar_correo(invitacion: Invitacion) -> None:
    contexto = {
        "invitacion": invitacion,
        "proyecto": invitacion.proyecto,
        "invitada_por": invitacion.invitada_por,
        "url": url_invitacion(invitacion),
    }
    asunto = render_to_string("proyectos/correos/invitacion_asunto.txt", contexto).strip()
    cuerpo = render_to_string("proyectos/correos/invitacion.txt", contexto)
    send_mail(asunto, cuerpo, None, [invitacion.correo])


def invitar(proyecto: Proyecto, por, correo: str) -> Invitacion:
    exigir_dueno(proyecto, por)
    exigir_activo(proyecto)
    correo = (correo or "").strip().lower()
    if not correo:
        raise ValidationError({"correo": "Escribe un correo."})
    if MiembroProyecto.objects.filter(proyecto=proyecto, usuario__email__iexact=correo).exists():
        raise ValidationError({"correo": "Esa persona ya es miembro del proyecto."})
    if proyecto.invitaciones.filter(
        estado=Invitacion.Estado.PENDIENTE, correo__iexact=correo
    ).exists():
        raise ValidationError(
            {"correo": "Ya hay una invitación pendiente para ese correo. Puedes reenviarla."}
        )
    invitacion = Invitacion(proyecto=proyecto, correo=correo, invitada_por=por)
    invitacion.full_clean()  # formato del correo
    invitacion.save()
    transaction.on_commit(lambda: _enviar_correo(invitacion))
    return invitacion


def reenviar_invitacion(invitacion: Invitacion, por) -> Invitacion:
    exigir_dueno(invitacion.proyecto, por)
    exigir_activo(invitacion.proyecto)
    if invitacion.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("Solo se reenvían invitaciones pendientes.")
    if invitacion.veces_enviada >= MAX_ENVIOS_INVITACION:
        raise ValidationError(f"Esta invitación ya se envió {MAX_ENVIOS_INVITACION} veces.")
    Invitacion.objects.filter(pk=invitacion.pk).update(
        enviada_en=timezone.now(), veces_enviada=F("veces_enviada") + 1
    )
    invitacion.refresh_from_db()
    transaction.on_commit(lambda: _enviar_correo(invitacion))
    return invitacion


def cancelar_invitacion(invitacion: Invitacion, por) -> Invitacion:
    exigir_dueno(invitacion.proyecto, por)
    if invitacion.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("La invitación ya no está pendiente.")
    invitacion.estado = Invitacion.Estado.CANCELADA
    invitacion.respondida_en = timezone.now()
    invitacion.save(update_fields=["estado", "respondida_en"])
    return invitacion


@transaction.atomic
def aceptar_invitacion(token: str, usuario) -> MiembroProyecto:
    """
    El enlace va al correo invitado, así que solo lo acepta una cuenta con ese mismo correo:
    quien reenvía el correo a otra persona no le da acceso al proyecto.
    """
    invitacion = (
        Invitacion.objects.select_for_update()
        .select_related("proyecto")
        .filter(token=token)
        .first()
    )
    if invitacion is None or invitacion.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("La invitación no existe, ya se usó o fue cancelada.")
    if usuario.email.lower() != invitacion.correo:
        raise PermisoDenegado(
            "Esta invitación es para otro correo. Entra con la cuenta de ese correo."
        )
    m, _ = MiembroProyecto.objects.get_or_create(proyecto=invitacion.proyecto, usuario=usuario)
    invitacion.estado = Invitacion.Estado.ACEPTADA
    invitacion.aceptada_por = usuario
    invitacion.respondida_en = timezone.now()
    invitacion.save(update_fields=["estado", "aceptada_por", "respondida_en"])
    return m


# ---------------------------------------------------------------------------------------------
# Tipos de tarjeta
# ---------------------------------------------------------------------------------------------


def _guardar_tipo(tipo: TipoTarjeta) -> TipoTarjeta:
    tipo.nombre = (tipo.nombre or "").strip()
    tipo.color = (tipo.color or "").strip().lower()
    if not tipo.nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    repetido = TipoTarjeta.objects.filter(proyecto=tipo.proyecto, nombre__iexact=tipo.nombre)
    if tipo.pk:
        repetido = repetido.exclude(pk=tipo.pk)
    if repetido.exists():
        raise ValidationError({"nombre": "Ya hay un tipo con ese nombre en este proyecto."})
    tipo.full_clean(exclude=["proyecto"])
    tipo.save()
    return tipo


def crear_tipo(
    proyecto: Proyecto, por, *, nombre: str, color: str, descripcion: str = ""
) -> TipoTarjeta:
    exigir_permiso(proyecto, por, "gestionar_tipos")
    return _guardar_tipo(
        TipoTarjeta(proyecto=proyecto, nombre=nombre, color=color, descripcion=descripcion)
    )


def editar_tipo(tipo: TipoTarjeta, por, **campos) -> TipoTarjeta:
    exigir_permiso(tipo.proyecto, por, "gestionar_tipos")
    for campo in ("nombre", "color", "descripcion"):
        if campo in campos:
            setattr(tipo, campo, campos[campo])
    return _guardar_tipo(tipo)


def eliminar_tipo(tipo: TipoTarjeta, por) -> None:
    """Lo quita de las tarjetas (se borran las filas del M2M); las tarjetas no se borran."""
    exigir_permiso(tipo.proyecto, por, "gestionar_tipos")
    tipo.delete()
