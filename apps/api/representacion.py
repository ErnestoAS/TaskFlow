"""
Cómo se ve cada objeto en la API (salida). La entrada la validan los servicios.

Se usan funciones y no serializers de DRF porque la salida mezcla datos calculados (permisos del
usuario, conteos, vencidas) y las reglas de entrada ya viven en `servicios.py`.
"""

from django.utils import timezone

from apps.proyectos.models import PERMISOS, Invitacion, MiembroProyecto
from apps.tarjetas.models import Estatus


def usuario(u):
    if u is None:
        return None
    nombre = u.nombre_completo or u.email.split("@")[0]
    partes = [p for p in nombre.replace(".", " ").split() if p]
    iniciales = "".join(p[0] for p in partes[:2]).upper() or u.email[:2].upper()
    return {"id": u.pk, "nombre": nombre, "correo": u.email, "iniciales": iniciales}


def permisos(m: MiembroProyecto | None) -> dict:
    return {p: bool(m and m.puede(p)) for p in PERMISOS}


def tipo(t, n_tarjetas=None):
    datos = {"id": t.pk, "nombre": t.nombre, "descripcion": t.descripcion, "color": t.color}
    if n_tarjetas is not None:
        datos["n_tarjetas"] = n_tarjetas
    return datos


def conteos(tarjetas_qs) -> dict:
    hoy = timezone.localdate()
    datos = {e: 0 for e in Estatus.values}
    for e in tarjetas_qs.values_list("estatus", flat=True):
        datos[e] += 1
    datos["vencidas"] = (
        tarjetas_qs.exclude(estatus=Estatus.FINALIZADA).filter(fecha_fin__lt=hoy).count()
    )
    return datos


def proyecto_resumen(p, yo):
    miembros = list(p.miembros.select_related("usuario"))
    mia = next((m for m in miembros if m.usuario_id == yo.pk), None)
    dueno = next((m.usuario for m in miembros if m.es_dueno), None)
    return {
        "id": p.pk,
        "nombre": p.nombre,
        "archivado": p.archivado,
        "rol": mia.rol if mia else None,
        "dueno": usuario(dueno),
        "miembros": [usuario(m.usuario) for m in miembros],
        "conteos": conteos(p.tarjetas.all()),
        "permisos": permisos(mia) if not p.archivado else {k: False for k in PERMISOS},
    }


def proyecto_detalle(p, yo):
    datos = proyecto_resumen(p, yo)
    es_dueno = datos["rol"] == MiembroProyecto.Rol.DUENO
    datos["miembros"] = [
        {"usuario": usuario(m.usuario), "rol": m.rol, "permisos": permisos(m)}
        for m in p.miembros.select_related("usuario").order_by(
            "rol", "usuario__nombre", "usuario__email"
        )
    ]
    datos["tipos"] = [tipo(t, t.tarjetas.count()) for t in p.tipos.all()]
    datos["invitaciones"] = (
        [
            {
                "id": i.pk,
                "correo": i.correo,
                "enviada_en": i.enviada_en,
                "veces_enviada": i.veces_enviada,
            }
            for i in p.invitaciones.filter(estado=Invitacion.Estado.PENDIENTE)
        ]
        if es_dueno
        else []
    )
    return datos


def cambio(c):
    return {
        "fecha": c.fecha,
        "usuario": usuario(c.usuario),
        "de": c.estatus_anterior or None,
        "a": c.estatus_nuevo,
    }


def tarjeta(t, con_historial=False):
    datos = {
        "id": t.pk,
        "proyecto": t.proyecto_id,
        "proyecto_nombre": t.proyecto.nombre,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "estatus": t.estatus,
        "prioridad": t.prioridad,
        "fecha_fin": t.fecha_fin.isoformat() if t.fecha_fin else None,
        "asignados": [usuario(u) for u in t.asignados.all()],
        "tipos": [tp.pk for tp in t.tipos.all()],
        "creada_por": usuario(t.creada_por),
        "creado_en": t.creado_en,
    }
    if con_historial:
        datos["historial"] = [cambio(c) for c in t.cambios_estatus.select_related("usuario")]
    return datos
