"""
Reglas de negocio de las tarjetas (§4.5 de la propuesta).

Todo cambio de estatus pasa por `cambiar_estatus` (o por `crear_tarjeta`, que registra la
creación), para que ninguno quede fuera del historial.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.proyectos.models import MiembroProyecto, Proyecto, TipoTarjeta
from apps.proyectos.servicios import exigir_permiso

from .models import CambioEstatus, Estatus, Prioridad, Tarjeta

CAMPOS_EDITABLES = ("titulo", "descripcion", "prioridad", "fecha_fin", "asignados", "tipos")


def _validar_asignados(proyecto: Proyecto, asignados) -> list:
    asignados = list(asignados or [])
    ids = {getattr(u, "pk", u) for u in asignados}
    miembros = set(
        MiembroProyecto.objects.filter(proyecto=proyecto, usuario_id__in=ids).values_list(
            "usuario_id", flat=True
        )
    )
    if ids - miembros:
        raise ValidationError({"asignados": "Solo se puede asignar a miembros del proyecto."})
    return list(ids)


def _validar_tipos(proyecto: Proyecto, tipos) -> list:
    ids = {getattr(t, "pk", t) for t in (tipos or [])}
    del_proyecto = set(
        TipoTarjeta.objects.filter(proyecto=proyecto, pk__in=ids).values_list("pk", flat=True)
    )
    if ids - del_proyecto:
        raise ValidationError({"tipos": "Solo se pueden usar tipos de este proyecto."})
    return list(ids)


def _validar_textos(titulo, descripcion) -> tuple[str, str]:
    titulo, descripcion = (titulo or "").strip(), (descripcion or "").strip()
    errores = {}
    if not titulo:
        errores["titulo"] = "Escribe un título."
    if not descripcion:
        errores["descripcion"] = "Escribe una descripción."
    if errores:
        raise ValidationError(errores)
    return titulo, descripcion


def _validar_prioridad(prioridad: str) -> str:
    if prioridad not in Prioridad.values:
        raise ValidationError({"prioridad": "Prioridad inválida."})
    return prioridad


def registrar_cambio(tarjeta: Tarjeta, usuario, anterior: str, nuevo: str) -> CambioEstatus:
    """Una fila del historial. `anterior=""` = creación. Lo usan los servicios y el admin."""
    return CambioEstatus.objects.create(
        tarjeta=tarjeta, usuario=usuario, estatus_anterior=anterior or "", estatus_nuevo=nuevo
    )


@transaction.atomic
def crear_tarjeta(
    proyecto: Proyecto,
    usuario,
    *,
    titulo: str,
    descripcion: str,
    prioridad: str = Prioridad.MEDIA,
    fecha_fin=None,
    asignados=(),
    tipos=(),
) -> Tarjeta:
    exigir_permiso(proyecto, usuario, "crear")
    titulo, descripcion = _validar_textos(titulo, descripcion)
    ids_asignados = _validar_asignados(proyecto, asignados)
    ids_tipos = _validar_tipos(proyecto, tipos)
    tarjeta = Tarjeta.objects.create(
        proyecto=proyecto,
        titulo=titulo,
        descripcion=descripcion,
        prioridad=_validar_prioridad(prioridad),
        fecha_fin=fecha_fin,
        creada_por=usuario,
    )
    tarjeta.asignados.set(ids_asignados)
    tarjeta.tipos.set(ids_tipos)
    registrar_cambio(tarjeta, usuario, "", tarjeta.estatus)
    return tarjeta


@transaction.atomic
def editar_tarjeta(tarjeta: Tarjeta, usuario, **campos) -> Tarjeta:
    """Edita título, descripción, prioridad, fecha fin, asignados y tipos (no el estatus)."""
    exigir_permiso(tarjeta.proyecto, usuario, "editar")
    desconocidos = set(campos) - set(CAMPOS_EDITABLES)
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    titulo, descripcion = _validar_textos(
        campos.get("titulo", tarjeta.titulo), campos.get("descripcion", tarjeta.descripcion)
    )
    tarjeta.titulo, tarjeta.descripcion = titulo, descripcion
    if "prioridad" in campos:
        tarjeta.prioridad = _validar_prioridad(campos["prioridad"])
    if "fecha_fin" in campos:
        tarjeta.fecha_fin = campos["fecha_fin"]
    tarjeta.save()
    if "asignados" in campos:
        tarjeta.asignados.set(_validar_asignados(tarjeta.proyecto, campos["asignados"]))
    if "tipos" in campos:
        tarjeta.tipos.set(_validar_tipos(tarjeta.proyecto, campos["tipos"]))
    return tarjeta


@transaction.atomic
def cambiar_estatus(tarjeta: Tarjeta, usuario, estatus: str) -> Tarjeta:
    """Mueve la tarjeta a cualquier estatus, también hacia atrás desde Finalizada (§4.5)."""
    exigir_permiso(tarjeta.proyecto, usuario, "cambiar_estatus")
    if estatus not in Estatus.values:
        raise ValidationError({"estatus": "Estatus inválido."})
    # Bloquea la fila: dos personas moviendo la misma tarjeta a la vez dejan un historial coherente.
    actual = Tarjeta.objects.select_for_update().get(pk=tarjeta.pk)
    if actual.estatus == estatus:
        return actual
    anterior = actual.estatus
    actual.estatus = estatus
    actual.save(update_fields=["estatus", "actualizado_en"])
    registrar_cambio(actual, usuario, anterior, estatus)
    tarjeta.estatus = estatus
    return actual


def eliminar_tarjeta(tarjeta: Tarjeta, usuario) -> None:
    """Borra la tarjeta y su historial (CASCADE)."""
    exigir_permiso(tarjeta.proyecto, usuario, "eliminar")
    tarjeta.delete()
