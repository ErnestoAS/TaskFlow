"""API de comentarios (2026-10-20, §6 y §7): comentar, editar, borrar y acceso."""

import pytest

from apps.actividades import servicios as st
from apps.pizarras import servicios as sp

API = "/api/v1"


def _post(c, url, datos=None):
    return c.post(f"{API}{url}", datos or {}, content_type="application/json")


def _patch(c, url, datos):
    return c.patch(f"{API}{url}", datos, content_type="application/json")


@pytest.fixture
def actividad(pizarra, dueno):
    return st.crear_actividad(pizarra, dueno, titulo="Con conversación")


def test_comentar_editar_y_borrar(client, dueno, actividad):
    client.force_login(dueno)
    r = _post(client, f"/actividades/{actividad.pk}/comentarios/", {"texto": "<b>Hola</b>"})
    assert r.status_code == 201, r.json()
    [c] = r.json()["comentarios"]
    # Texto plano, tal cual: lo escapa la PWA al pintarlo.
    assert (c["texto"], c["autor"]["id"], c["editado_en"]) == ("<b>Hola</b>", dueno.pk, None)
    assert r.json()["n_comentarios"] == 1
    r = _patch(client, f"/comentarios/{c['id']}/", {"texto": "Hola de nuevo"})
    assert r.status_code == 200
    assert r.json()["comentarios"][0]["texto"] == "Hola de nuevo"
    assert r.json()["comentarios"][0]["editado_en"] is not None
    r = client.delete(f"{API}/comentarios/{c['id']}/")
    assert r.status_code == 200 and r.json()["comentarios"] == []


def test_el_mas_reciente_va_primero_y_el_tablero_trae_el_conteo(client, dueno, actividad, pizarra):
    st.comentar(actividad, dueno, "primero")
    st.comentar(actividad, dueno, "segundo")
    client.force_login(dueno)
    detalle = client.get(f"{API}/actividades/{actividad.pk}/").json()
    assert [c["texto"] for c in detalle["comentarios"]] == ["segundo", "primero"]
    [en_tablero] = client.get(f"{API}/pizarras/{pizarra.pk}/actividades/").json()
    assert en_tablero["n_comentarios"] == 2 and "comentarios" not in en_tablero


def test_texto_vacio_es_400_por_campo(client, dueno, actividad):
    client.force_login(dueno)
    r = _post(client, f"/actividades/{actividad.pk}/comentarios/", {"texto": "  "})
    assert r.status_code == 400 and "texto" in r.json()


def test_comentario_ajeno_es_404_y_sin_derecho_es_403(
    client, dueno, actividad, crear_usuario, agregar_miembro
):
    c = st.comentar(actividad, dueno, "del dueño")
    nuevo = f"/actividades/{actividad.pk}/comentarios/"
    client.force_login(crear_usuario())  # no es miembro
    assert _post(client, nuevo, {"texto": "x"}).status_code == 404
    assert _patch(client, f"/comentarios/{c.pk}/", {"texto": "x"}).status_code == 404
    assert client.delete(f"{API}/comentarios/{c.pk}/").status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, editar=False)
    client.force_login(luis)
    # Comenta aunque no pueda editar, pero no toca el comentario de otro.
    assert _post(client, nuevo, {"texto": "x"}).status_code == 201
    assert _patch(client, f"/comentarios/{c.pk}/", {"texto": "x"}).status_code == 403
    assert client.delete(f"{API}/comentarios/{c.pk}/").status_code == 403


def test_pizarra_archivada_no_admite_comentarios(client, dueno, actividad, pizarra):
    sp.archivar(pizarra, dueno)
    client.force_login(dueno)
    r = _post(client, f"/actividades/{actividad.pk}/comentarios/", {"texto": "x"})
    assert r.status_code == 403
