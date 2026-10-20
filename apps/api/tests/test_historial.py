"""Historial de la pizarra (2026-10-20, §5 y §6): qué trae, filtro por persona, páginas y acceso."""

from apps.actividades import servicios as st
from apps.actividades.models import Movimiento
from apps.pizarras import servicios as sp

API = "/api/v1"


def _historial(client, pizarra, **params):
    return client.get(f"{API}/pizarras/{pizarra.pk}/historial/", params)


def test_trae_creaciones_movimientos_comentarios_y_eliminaciones(
    client, dueno, pizarra, listas, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis, eliminar=True)
    sillas = st.crear_actividad(pizarra, dueno, titulo="Comprar sillas")
    st.mover_actividad(sillas, luis, listas["En curso"])
    st.comentar(sillas, dueno, "Ya hay presupuesto")
    gafetes = st.crear_actividad(pizarra, dueno, titulo="Imprimir gafetes")
    st.eliminar_actividad(gafetes, luis)
    client.force_login(dueno)
    r = _historial(client, pizarra)
    assert r.status_code == 200
    entradas = r.json()["entradas"]
    assert [(e["tipo"], e["actividad"]["titulo"], e["de"], e["a"]) for e in entradas] == [
        ("movimiento", "Imprimir gafetes", "Pendiente", None),  # la eliminó
        ("movimiento", "Imprimir gafetes", None, "Pendiente"),
        ("comentario", "Comprar sillas", None, None),
        ("movimiento", "Comprar sillas", "Pendiente", "En curso"),
        ("movimiento", "Comprar sillas", None, "Pendiente"),
    ]
    # La eliminada ya no se puede abrir, pero dice quién la eliminó.
    assert entradas[0]["actividad"]["id"] is None and entradas[0]["usuario"]["id"] == luis.pk
    assert entradas[2]["texto"] == "Ya hay presupuesto"
    assert entradas[3]["actividad"]["id"] == sillas.pk
    assert r.json()["mas"] is False
    # Solo lo de Luis: la eliminación y el movimiento.
    r = _historial(client, pizarra, persona=luis.pk)
    assert [(e["de"], e["a"]) for e in r.json()["entradas"]] == [
        ("Pendiente", None),
        ("Pendiente", "En curso"),
    ]


def test_eliminar_conserva_el_historial_sin_enlace(pizarra, dueno, listas):
    a = st.crear_actividad(pizarra, dueno, titulo="Rentar salón")
    st.mover_actividad(a, dueno, listas["En curso"])
    st.eliminar_actividad(a, dueno)
    filas = Movimiento.objects.filter(pizarra=pizarra).order_by("fecha", "id")
    assert [(m.actividad_id, m.titulo, m.lista_anterior, m.lista_nueva) for m in filas] == [
        (None, "Rentar salón", "", "Pendiente"),
        (None, "Rentar salón", "Pendiente", "En curso"),
        (None, "Rentar salón", "En curso", ""),
    ]


def test_el_titulo_es_el_actual_mientras_exista(client, dueno, pizarra):
    a = st.crear_actividad(pizarra, dueno, titulo="Borrador")
    st.editar_actividad(a, dueno, titulo="Definitivo")
    client.force_login(dueno)
    [e] = _historial(client, pizarra).json()["entradas"]
    assert e["actividad"] == {"id": a.pk, "titulo": "Definitivo"}


def test_paginas_con_antes(client, dueno, pizarra, monkeypatch):
    monkeypatch.setattr(st, "HISTORIAL_POR_PAGINA", 2)
    for titulo in ("a", "b", "c"):
        st.crear_actividad(pizarra, dueno, titulo=titulo)
    client.force_login(dueno)
    r = _historial(client, pizarra).json()
    assert [e["actividad"]["titulo"] for e in r["entradas"]] == ["c", "b"] and r["mas"]
    r = _historial(client, pizarra, antes=r["entradas"][-1]["fecha"]).json()
    assert [e["actividad"]["titulo"] for e in r["entradas"]] == ["a"] and not r["mas"]


def test_solo_miembros_tambien_archivada_y_parametros_invalidos(
    client, dueno, pizarra, crear_usuario
):
    st.crear_actividad(pizarra, dueno, titulo="a")
    client.force_login(crear_usuario())
    assert _historial(client, pizarra).status_code == 404
    sp.archivar(pizarra, dueno)
    client.force_login(dueno)
    assert _historial(client, pizarra).status_code == 200
    assert _historial(client, pizarra, antes="ayer").status_code == 400
    assert _historial(client, pizarra, persona="luis").status_code == 400
