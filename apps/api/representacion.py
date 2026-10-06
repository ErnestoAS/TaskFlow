"""
Cómo se ve cada objeto en la API (salida). La entrada la validan los servicios.

Se usan funciones y no serializers de DRF porque la salida mezcla datos calculados (permisos del
usuario, conteos, vencidas, checklist hecha) y las reglas de entrada ya viven en `servicios.py`.
"""

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


def tipo(t, n_tarjetas=None):
    datos = {"id": t.pk, "nombre": t.nombre, "descripcion": t.descripcion, "color": t.color}
    if n_tarjetas is not None:
        datos["n_tarjetas"] = n_tarjetas
    return datos


def lista(lst, n_tarjetas=None):
    datos = {
        "id": lst.pk,
        "nombre": lst.nombre,
        "posicion": lst.posicion,
    }
    if n_tarjetas is not None:
        datos["n_tarjetas"] = n_tarjetas
    return datos


def conteos(p, yo) -> dict:
    """Resumen de tamaño fijo para «Mis pizarras» (§4.6): no crece con el número de listas."""
    tarjetas = p.tarjetas.all()
    return {
        "tarjetas": tarjetas.count(),
        "listas": p.listas.count(),
        "mias": tarjetas.filter(asignados=yo).count(),
        "vencidas": tarjetas.filter(fecha_fin__lt=timezone.localdate()).count(),
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
    datos["listas"] = [lista(lst, lst.tarjetas.count()) for lst in p.listas.all()]
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


def movimiento(m):
    return {
        "fecha": m.fecha,
        "usuario": usuario(m.usuario),
        "de": m.lista_anterior or None,
        "a": m.lista_nueva or None,
        "nota": m.nota or None,
    }


def elemento(e):
    hija = e.tarjeta_creada
    return {
        "id": e.pk,
        "texto": e.texto,
        "hecho": e.esta_hecho,
        "automatico": e.automatico,
        "tarjeta": (
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
    return {"id": origen.tarjeta_id, "titulo": origen.tarjeta.titulo, "elemento": origen.texto}


def tarjeta(t, con_detalle=False):
    elementos = list(t.checklist.all())
    datos = {
        "id": t.pk,
        "pizarra": t.pizarra_id,
        "pizarra_nombre": t.pizarra.nombre,
        "lista": t.lista_id,
        "lista_nombre": t.lista.nombre,
        "lista_terminado": t.lista_terminado_id,
        "posicion": t.posicion,
        "titulo": t.titulo,
        "descripcion": t.descripcion,
        "prioridad": t.prioridad,
        "fecha_inicio": t.fecha_inicio.isoformat(),
        "fecha_fin": t.fecha_fin.isoformat() if t.fecha_fin else None,
        "asignados": [usuario(u) for u in t.asignados.all()],
        "tipos": [tp.pk for tp in t.tipos.all()],
        "creada_por": usuario(t.creada_por),
        "creado_en": t.creado_en,
        "checklist_conteo": (
            {"hechos": sum(e.esta_hecho for e in elementos), "total": len(elementos)}
            if elementos
            else None
        ),
        "viene_de": _viene_de(t),
    }
    if con_detalle:
        datos["checklist"] = [elemento(e) for e in elementos]
        datos["historial"] = [movimiento(m) for m in t.movimientos.select_related("usuario")]
    return datos
