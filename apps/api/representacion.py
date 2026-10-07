"""
Cómo se ve cada objeto en la API (salida). La entrada la validan los servicios.

Se usan funciones y no serializers de DRF porque la salida mezcla datos calculados (permisos del
usuario, conteos, vencidas, checklist hecha) y las reglas de entrada ya viven en `servicios.py`.
"""

from django.conf import settings
from django.utils import timezone

from apps.pizarras.models import PERMISOS, Invitacion, MiembroPizarra


def usuario(u):
    if u is None:
        return None
    nombre = u.nombre_completo or u.email.split("@")[0]
    partes = [p for p in nombre.replace(".", " ").split() if p]
    iniciales = "".join(p[0] for p in partes[:2]).upper() or u.email[:2].upper()
    return {"id": u.pk, "nombre": nombre, "correo": u.email, "iniciales": iniciales}


def permisos(m: MiembroPizarra | None) -> dict:
    return {p: bool(m and m.puede(p)) for p in PERMISOS}


def tipo(t, n_actividades=None):
    datos = {"id": t.pk, "nombre": t.nombre, "descripcion": t.descripcion, "color": t.color}
    if n_actividades is not None:
        datos["n_actividades"] = n_actividades
    return datos


def solicitante(t):
    """«Solicitada por» de una actividad (Etapa 3.8): un miembro o un externo del catálogo."""
    if t.solicitada_por_id:
        return {
            "tipo": "miembro",
            "id": t.solicitada_por_id,
            "nombre": usuario(t.solicitada_por)["nombre"],
        }
    if t.solicitante_externo_id:
        return {
            "tipo": "externo",
            "id": t.solicitante_externo_id,
            "nombre": t.solicitante_externo.nombre,
        }
    return None


def adjunto(a):
    """La descarga es `GET adjuntos/<id>/` (la PWA arma la ruta): no hay URL pública (§7)."""
    return {
        "id": a.pk,
        "nombre": a.nombre,
        "tamano": a.tamano,
        "tipo": a.tipo,
        "subido_por": usuario(a.subido_por),
        "creado_en": a.creado_en,
    }


def lista(lst, n_actividades=None):
    datos = {
        "id": lst.pk,
        "nombre": lst.nombre,
        "posicion": lst.posicion,
    }
    if n_actividades is not None:
        datos["n_actividades"] = n_actividades
    return datos


def conteos(p, yo) -> dict:
    """Resumen de tamaño fijo para «Mis pizarras» (§4.6): no crece con el número de listas."""
    actividades = p.actividades.all()
    return {
        "actividades": actividades.count(),
        "listas": p.listas.count(),
        "mias": actividades.filter(asignados=yo).count(),
        "vencidas": actividades.filter(fecha_fin__lt=timezone.localdate()).count(),
    }


def pizarra_resumen(p, yo):
    miembros = list(p.miembros.select_related("usuario"))
    mia = next((m for m in miembros if m.usuario_id == yo.pk), None)
    dueno = next((m.usuario for m in miembros if m.es_dueno), None)
    return {
        "id": p.pk,
        "nombre": p.nombre,
        "archivada": p.archivada,
        "rol": mia.rol if mia else None,
        "dueno": usuario(dueno),
        "miembros": [usuario(m.usuario) for m in miembros],
        "conteos": conteos(p, yo),
        "permisos": permisos(mia) if not p.archivada else {k: False for k in PERMISOS},
    }


def pizarra_detalle(p, yo):
    datos = pizarra_resumen(p, yo)
    es_dueno = datos["rol"] == MiembroPizarra.Rol.DUENO
    datos["miembros"] = [
        {"usuario": usuario(m.usuario), "rol": m.rol, "permisos": permisos(m)}
        for m in p.miembros.select_related("usuario").order_by(
            "rol", "usuario__nombre", "usuario__email"
        )
    ]
    datos["listas"] = [lista(lst, lst.actividades.count()) for lst in p.listas.all()]
    datos["tipos"] = [tipo(t, t.actividades.count()) for t in p.tipos.all()]
    from apps.actividades.servicios import MB, espacio_adjuntos

    datos["adjuntos_espacio"] = {
        "usado": espacio_adjuntos(p),
        "limite": settings.TASKFLOW_ADJUNTOS_PIZARRA_MB * MB,
        "max_archivo": settings.TASKFLOW_ADJUNTO_MAX_MB * MB,
    }
    datos["solicitantes"] = [
        {"id": s.pk, "nombre": s.nombre, "n_actividades": s.actividades.count()}
        for s in p.solicitantes.all()
    ]
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


def movimiento(m):
    return {
        "fecha": m.fecha,
        "usuario": usuario(m.usuario),
        "de": m.lista_anterior or None,
        "a": m.lista_nueva or None,
        "nota": m.nota or None,
    }


def elemento(e):
    hija = e.actividad_creada
    return {
        "id": e.pk,
        "texto": e.texto,
        "hecho": e.esta_hecho,
        "automatico": e.automatico,
        "actividad": (
            {
                "id": hija.pk,
                "titulo": hija.titulo,
                "lista": hija.lista_id,
                "lista_nombre": hija.lista.nombre,
            }
            if hija
            else None
        ),
    }


def _viene_de(t):
    origen = getattr(t, "elemento_origen", None)
    if origen is None:
        return None
    return {"id": origen.actividad_id, "titulo": origen.actividad.titulo, "elemento": origen.texto}


def actividad(t, con_detalle=False):
    elementos = list(t.checklist.all())
    datos = {
        "id": t.pk,
        "pizarra": t.pizarra_id,
        "pizarra_nombre": t.pizarra.nombre,
        "lista": t.lista_id,
        "lista_nombre": t.lista.nombre,
        "lista_terminado": t.lista_terminado_id,
        "lista_al_completar": t.lista_al_completar_id,
        "posicion": t.posicion,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "fecha_solicitud": t.fecha_solicitud.isoformat() if t.fecha_solicitud else None,
        "fecha_fin": t.fecha_fin.isoformat() if t.fecha_fin else None,
        "asignados": [usuario(u) for u in t.asignados.all()],
        "tipos": [tp.pk for tp in t.tipos.all()],
        "solicitante": solicitante(t),
        "creada_por": usuario(t.creada_por),
        "creado_en": t.creado_en,
        "checklist_conteo": (
            {"hechos": sum(e.esta_hecho for e in elementos), "total": len(elementos)}
            if elementos
            else None
        ),
        "viene_de": _viene_de(t),
        "n_adjuntos": len(t.adjuntos.all()),
    }
    if con_detalle:
        datos["checklist"] = [elemento(e) for e in elementos]
        datos["historial"] = [movimiento(m) for m in t.movimientos.select_related("usuario")]
        datos["adjuntos"] = [adjunto(a) for a in t.adjuntos.all()]
    return datos
