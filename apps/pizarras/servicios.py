"""
Reglas de negocio de pizarras, miembros, invitaciones, listas y tipos (§4.5 y §4.6).

Toda acción pasa por aquí: la API solo traduce la petición y llama a estas funciones. Así las
reglas viven en un solo lugar y se prueban sin HTTP.

- `PermisoDenegado`: el usuario no puede hacer eso (no es miembro, no es dueño, le falta el
  permiso o la pizarra está archivada). La API lo traduce a 403.
- `ValidationError`: la petición tiene datos inválidos (correo repetido, tipo de otra pizarra…).
  La API lo traduce a 400.
"""

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from .models import (
    PERMISOS,
    Invitacion,
    Lista,
    MiembroPizarra,
    Pizarra,
    TipoTarjeta,
)

# Tope de reenvíos de una misma invitación: las invitaciones no vencen y se pueden reenviar
# (decidido 2026-10-01); el tope solo evita usar el sistema para mandar correo masivo.
MAX_ENVIOS_INVITACION = 10


class PermisoDenegado(PermissionDenied):
    """El usuario no puede realizar la acción sobre la pizarra."""


# ---------------------------------------------------------------------------------------------
# Consultas de membresía y permisos
# ---------------------------------------------------------------------------------------------


def membresia(pizarra: Pizarra, usuario) -> MiembroPizarra | None:
    if not getattr(usuario, "is_authenticated", False):
        return None
    return MiembroPizarra.objects.filter(pizarra=pizarra, usuario=usuario).first()


def exigir_miembro(pizarra: Pizarra, usuario) -> MiembroPizarra:
    m = membresia(pizarra, usuario)
    if m is None:
        raise PermisoDenegado("No eres miembro de esta pizarra.")
    return m


def exigir_activa(pizarra: Pizarra) -> None:
    if pizarra.archivada:
        raise PermisoDenegado("La pizarra está archivada: es de solo lectura.")


def exigir_dueno(pizarra: Pizarra, usuario) -> MiembroPizarra:
    m = exigir_miembro(pizarra, usuario)
    if not m.es_dueno:
        raise PermisoDenegado("Solo el dueño de la pizarra puede hacer esto.")
    return m


def exigir_permiso(pizarra: Pizarra, usuario, permiso: str) -> MiembroPizarra:
    """Miembro, pizarra activa y permiso concedido (el dueño siempre lo tiene)."""
    m = exigir_miembro(pizarra, usuario)
    exigir_activa(pizarra)
    if not m.puede(permiso):
        raise PermisoDenegado("El dueño de la pizarra no te ha dado permiso para hacer esto.")
    return m


# ---------------------------------------------------------------------------------------------
# Pizarras
# ---------------------------------------------------------------------------------------------


@transaction.atomic
def crear_pizarra(usuario, nombre: str) -> Pizarra:
    """La crea sin listas (2026-10-06): cada quien arma las suyas desde el tablero."""
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    pizarra = Pizarra.objects.create(nombre=nombre, creado_por=usuario)
    MiembroPizarra.objects.create(pizarra=pizarra, usuario=usuario, rol=MiembroPizarra.Rol.DUENO)
    return pizarra


def renombrar_pizarra(pizarra: Pizarra, por, nombre: str) -> Pizarra:
    exigir_dueno(pizarra, por)
    exigir_activa(pizarra)
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    pizarra.nombre = nombre
    pizarra.save(update_fields=["nombre", "actualizado_en"])
    return pizarra


def archivar(pizarra: Pizarra, por) -> Pizarra:
    exigir_dueno(pizarra, por)
    if not pizarra.archivada:
        pizarra.archivada_en = timezone.now()
        pizarra.save(update_fields=["archivada_en", "actualizado_en"])
    return pizarra


def restaurar(pizarra: Pizarra, por) -> Pizarra:
    exigir_dueno(pizarra, por)
    if pizarra.archivada:
        pizarra.archivada_en = None
        pizarra.save(update_fields=["archivada_en", "actualizado_en"])
    return pizarra


def eliminar_pizarra(pizarra: Pizarra, por) -> None:
    """Borra la pizarra con sus tarjetas, listas, tipos, miembros e invitaciones (CASCADE)."""
    exigir_dueno(pizarra, por)
    pizarra.delete()


@transaction.atomic
def transferir(pizarra: Pizarra, por, nuevo_dueno, *, como_administrador: bool = False) -> None:
    """
    Pasa la pizarra a otro miembro. El dueño anterior queda como miembro con todos los permisos.

    `como_administrador=True` es para el admin de Django (dueño con la cuenta desactivada, §4.5):
    entonces `por` debe ser staff y no hace falta que sea el dueño.
    """
    if como_administrador:
        if not getattr(por, "is_staff", False):
            raise PermisoDenegado("Solo un administrador puede transferir una pizarra ajena.")
    else:
        exigir_dueno(pizarra, por)
    actual = MiembroPizarra.objects.select_for_update().get(
        pizarra=pizarra, rol=MiembroPizarra.Rol.DUENO
    )
    nuevo = (
        MiembroPizarra.objects.select_for_update()
        .filter(pizarra=pizarra, usuario=nuevo_dueno)
        .first()
    )
    if nuevo is None:
        raise ValidationError("Solo se puede transferir a un miembro de la pizarra.")
    if nuevo.pk == actual.pk:
        return
    # Orden obligado por la restricción «un solo dueño»: primero bajar, luego subir.
    actual.rol = MiembroPizarra.Rol.MIEMBRO
    for permiso in PERMISOS:
        setattr(actual, f"puede_{permiso}", True)
    actual.save()
    nuevo.rol = MiembroPizarra.Rol.DUENO
    nuevo.save(update_fields=["rol"])


# ---------------------------------------------------------------------------------------------
# Miembros
# ---------------------------------------------------------------------------------------------


def cambiar_permisos(pizarra: Pizarra, por, usuario, **permisos: bool) -> MiembroPizarra:
    """`cambiar_permisos(p, dueno, luis, eliminar=True, gestionar_tipos=False)`."""
    exigir_dueno(pizarra, por)
    exigir_activa(pizarra)
    desconocidos = set(permisos) - set(PERMISOS)
    if desconocidos:
        raise ValidationError(f"Permisos desconocidos: {', '.join(sorted(desconocidos))}.")
    m = exigir_miembro(pizarra, usuario)
    if m.es_dueno:
        raise ValidationError("El dueño siempre tiene todos los permisos.")
    for permiso, valor in permisos.items():
        setattr(m, f"puede_{permiso}", bool(valor))
    m.save()
    return m


def _desasignar(pizarra: Pizarra, usuario) -> None:
    # Import local: tarjetas depende de pizarras, no al revés.
    from apps.tarjetas.models import Tarjeta

    for tarjeta in Tarjeta.objects.filter(pizarra=pizarra, asignados=usuario):
        tarjeta.asignados.remove(usuario)


@transaction.atomic
def quitar_miembro(pizarra: Pizarra, por, usuario) -> None:
    exigir_dueno(pizarra, por)
    exigir_activa(pizarra)
    m = exigir_miembro(pizarra, usuario)
    if m.es_dueno:
        raise ValidationError("No se puede quitar al dueño. Primero transfiere la pizarra.")
    _desasignar(pizarra, usuario)
    m.delete()


@transaction.atomic
def salir(pizarra: Pizarra, usuario) -> None:
    m = exigir_miembro(pizarra, usuario)
    if m.es_dueno:
        raise ValidationError(
            "El dueño no puede salir. Primero transfiere la pizarra a otro miembro."
        )
    _desasignar(pizarra, usuario)
    m.delete()


# ---------------------------------------------------------------------------------------------
# Invitaciones
# ---------------------------------------------------------------------------------------------


def url_invitacion(invitacion: Invitacion) -> str:
    # Ruta de la PWA que acepta la invitación. La PWA usa rutas con # (§5), así que el enlace
    # funciona igual con o sin prefijo. TASKFLOW_URL ya incluye el prefijo, si lo hay.
    return f"{settings.TASKFLOW_URL.rstrip('/')}/app/#/invitacion/{invitacion.token}"


def _enviar_correo(invitacion: Invitacion) -> None:
    contexto = {
        "invitacion": invitacion,
        "pizarra": invitacion.pizarra,
        "invitada_por": invitacion.invitada_por,
        "url": url_invitacion(invitacion),
    }
    asunto = render_to_string("pizarras/correos/invitacion_asunto.txt", contexto).strip()
    cuerpo = render_to_string("pizarras/correos/invitacion.txt", contexto)
    send_mail(asunto, cuerpo, None, [invitacion.correo])


def invitar(pizarra: Pizarra, por, correo: str) -> Invitacion:
    exigir_dueno(pizarra, por)
    exigir_activa(pizarra)
    correo = (correo or "").strip().lower()
    if not correo:
        raise ValidationError({"correo": "Escribe un correo."})
    if MiembroPizarra.objects.filter(pizarra=pizarra, usuario__email__iexact=correo).exists():
        raise ValidationError({"correo": "Esa persona ya es miembro de la pizarra."})
    if pizarra.invitaciones.filter(
        estado=Invitacion.Estado.PENDIENTE, correo__iexact=correo
    ).exists():
        raise ValidationError(
            {"correo": "Ya hay una invitación pendiente para ese correo. Puedes reenviarla."}
        )
    invitacion = Invitacion(pizarra=pizarra, correo=correo, invitada_por=por)
    invitacion.full_clean()  # formato del correo
    invitacion.save()
    transaction.on_commit(lambda: _enviar_correo(invitacion))
    return invitacion


def reenviar_invitacion(invitacion: Invitacion, por) -> Invitacion:
    exigir_dueno(invitacion.pizarra, por)
    exigir_activa(invitacion.pizarra)
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
    exigir_dueno(invitacion.pizarra, por)
    if invitacion.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("La invitación ya no está pendiente.")
    invitacion.estado = Invitacion.Estado.CANCELADA
    invitacion.respondida_en = timezone.now()
    invitacion.save(update_fields=["estado", "respondida_en"])
    return invitacion


@transaction.atomic
def aceptar_invitacion(token: str, usuario) -> MiembroPizarra:
    """
    El enlace va al correo invitado, así que solo lo acepta una cuenta con ese mismo correo:
    quien reenvía el correo a otra persona no le da acceso a la pizarra.
    """
    invitacion = (
        Invitacion.objects.select_for_update().select_related("pizarra").filter(token=token).first()
    )
    if invitacion is None or invitacion.estado != Invitacion.Estado.PENDIENTE:
        raise ValidationError("La invitación no existe, ya se usó o fue cancelada.")
    if usuario.email.lower() != invitacion.correo:
        raise PermisoDenegado(
            "Esta invitación es para otro correo. Entra con la cuenta de ese correo."
        )
    m, _ = MiembroPizarra.objects.get_or_create(pizarra=invitacion.pizarra, usuario=usuario)
    invitacion.estado = Invitacion.Estado.ACEPTADA
    invitacion.aceptada_por = usuario
    invitacion.respondida_en = timezone.now()
    invitacion.save(update_fields=["estado", "aceptada_por", "respondida_en"])
    return m


# ---------------------------------------------------------------------------------------------
# Listas (§4.6): crear, renombrar, marcar de cierre, ordenar y eliminar (solo vacías)
# ---------------------------------------------------------------------------------------------


def _validar_nombre_lista(pizarra: Pizarra, nombre: str, propia: Lista | None = None) -> str:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    if len(nombre) > 50:
        raise ValidationError({"nombre": "Máximo 50 caracteres."})
    repetida = Lista.objects.filter(pizarra=pizarra, nombre__iexact=nombre)
    if propia:
        repetida = repetida.exclude(pk=propia.pk)
    if repetida.exists():
        raise ValidationError({"nombre": "Ya hay una lista con ese nombre en esta pizarra."})
    return nombre


@transaction.atomic
def crear_lista(pizarra: Pizarra, por, nombre: str) -> Lista:
    """La agrega al final del tablero."""
    exigir_permiso(pizarra, por, "gestionar_listas")
    nombre = _validar_nombre_lista(pizarra, nombre)
    ultima = pizarra.listas.order_by("-posicion").values_list("posicion", flat=True).first()
    return Lista.objects.create(
        pizarra=pizarra, nombre=nombre, posicion=0 if ultima is None else ultima + 1
    )


def editar_lista(lista: Lista, por, **campos) -> Lista:
    """Cambia `nombre`."""
    exigir_permiso(lista.pizarra, por, "gestionar_listas")
    desconocidos = set(campos) - {"nombre"}
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    if "nombre" in campos:
        lista.nombre = _validar_nombre_lista(lista.pizarra, campos["nombre"], propia=lista)
    lista.save()
    return lista


@transaction.atomic
def ordenar_listas(pizarra: Pizarra, por, ids: list[int]) -> list[Lista]:
    """`ids` = todas las listas de la pizarra en el orden nuevo."""
    exigir_permiso(pizarra, por, "gestionar_listas")
    listas = {lista.pk: lista for lista in pizarra.listas.select_for_update()}
    try:
        ids = [int(i) for i in ids or []]
    except (TypeError, ValueError) as e:
        raise ValidationError({"ids": "Orden inválido."}) from e
    if sorted(ids) != sorted(listas):
        raise ValidationError({"ids": "El orden debe incluir todas las listas de la pizarra."})
    for posicion, pk in enumerate(ids):
        listas[pk].posicion = posicion
    Lista.objects.bulk_update(listas.values(), ["posicion"])
    return [listas[pk] for pk in ids]


def eliminar_lista(lista: Lista, por) -> None:
    """Solo una lista vacía: borrar en cascada tarjetas al quitar una columna es muy fácil."""
    exigir_permiso(lista.pizarra, por, "gestionar_listas")
    n = lista.tarjetas.count()
    if n:
        raise ValidationError(
            f"La lista tiene {n} tarjeta{'s' if n != 1 else ''}: muévelas o elimínalas antes."
        )
    from apps.tarjetas.models import ElementoChecklist

    # Las checklists que se marcaban al llegar aquí pasan a palomeo manual (SET_NULL) con el
    # estado que tenían: como la lista está vacía, ninguna tarjeta enlazada estaba en ella.
    ElementoChecklist.objects.filter(
        tarjeta__lista_terminado=lista, tarjeta_creada__isnull=False
    ).update(hecho=False)
    lista.delete()


# ---------------------------------------------------------------------------------------------
# Tipos de tarjeta
# ---------------------------------------------------------------------------------------------


def _guardar_tipo(tipo: TipoTarjeta) -> TipoTarjeta:
    tipo.nombre = (tipo.nombre or "").strip()
    tipo.color = (tipo.color or "").strip().lower()
    if not tipo.nombre:
        raise ValidationError({"nombre": "Escribe un nombre."})
    repetido = TipoTarjeta.objects.filter(pizarra=tipo.pizarra, nombre__iexact=tipo.nombre)
    if tipo.pk:
        repetido = repetido.exclude(pk=tipo.pk)
    if repetido.exists():
        raise ValidationError({"nombre": "Ya hay un tipo con ese nombre en esta pizarra."})
    tipo.full_clean(exclude=["pizarra"])
    tipo.save()
    return tipo


def crear_tipo(
    pizarra: Pizarra, por, *, nombre: str, color: str, descripcion: str = ""
) -> TipoTarjeta:
    exigir_permiso(pizarra, por, "gestionar_tipos")
    return _guardar_tipo(
        TipoTarjeta(pizarra=pizarra, nombre=nombre, color=color, descripcion=descripcion)
    )


def editar_tipo(tipo: TipoTarjeta, por, **campos) -> TipoTarjeta:
    exigir_permiso(tipo.pizarra, por, "gestionar_tipos")
    for campo in ("nombre", "color", "descripcion"):
        if campo in campos:
            setattr(tipo, campo, campos[campo])
    return _guardar_tipo(tipo)


def eliminar_tipo(tipo: TipoTarjeta, por) -> None:
    """Lo quita de las tarjetas (se borran las filas del M2M); las tarjetas no se borran."""
    exigir_permiso(tipo.pizarra, por, "gestionar_tipos")
    tipo.delete()
