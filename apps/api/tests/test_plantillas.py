"""Plantillas de listas al crear una pizarra y en una pizarra vacía (2026-10-20, §6)."""

from apps.pizarras import servicios as sp

API = "/api/v1"


def _post(c, url, datos=None):
    return c.post(f"{API}{url}", datos or {}, content_type="application/json")


def _listas(r):
    return [lista["nombre"] for lista in r.json()["listas"]]


def test_crear_con_plantilla_y_sin_ella(client, dueno):
    client.force_login(dueno)
    r = _post(client, "/pizarras/", {"nombre": "Feria", "plantilla": "basica"})
    assert r.status_code == 201 and _listas(r) == ["Pendiente", "En curso", "Finalizada"]
    # Sin `plantilla`, como antes: vacía.
    r = _post(client, "/pizarras/", {"nombre": "Libre"})
    assert r.status_code == 201 and _listas(r) == []
    r = _post(client, "/pizarras/", {"nombre": "Rara", "plantilla": "kanban"})
    assert r.status_code == 400 and "plantilla" in r.json()


def test_copiar_solo_de_una_pizarra_propia(client, dueno, pizarra, crear_usuario):
    client.force_login(dueno)
    datos = {"nombre": "Copia", "plantilla": "copiar", "copiar_de": pizarra.pk}
    r = _post(client, "/pizarras/", datos)
    assert r.status_code == 201 and _listas(r) == ["Pendiente", "En curso", "Finalizada"]
    client.force_login(crear_usuario())
    r = _post(client, "/pizarras/", datos)
    assert r.status_code == 400 and "copiar_de" in r.json()


def test_usar_plantilla_en_una_pizarra_vacia(
    client, dueno, pizarra, crear_usuario, agregar_miembro
):
    vacia = sp.crear_pizarra(dueno, "Vacía")
    url = f"/pizarras/{vacia.pk}/listas/plantilla/"
    client.force_login(crear_usuario())  # no es miembro
    assert _post(client, url, {"plantilla": "basica"}).status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, p=vacia)  # sin «Gestionar listas»
    client.force_login(luis)
    assert _post(client, url, {"plantilla": "basica"}).status_code == 403
    client.force_login(dueno)
    r = _post(client, url, {"plantilla": "con_revision"})
    assert r.status_code == 200
    assert _listas(r) == ["Pendiente", "En curso", "En revisión", "Finalizada"]
    # Ya tiene listas: no se encima otra plantilla.
    assert _post(client, url, {"plantilla": "basica"}).status_code == 400
    con_listas = f"/pizarras/{pizarra.pk}/listas/plantilla/"
    assert _post(client, con_listas, {"plantilla": "basica"}).status_code == 400
