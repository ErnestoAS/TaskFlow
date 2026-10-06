import datetime
import re

import pytest
from django.test import Client

from apps.pizarras import servicios as sp
from apps.tarjetas import servicios as st
from apps.tarjetas.models import Tarjeta

pytestmark = pytest.mark.django_db
API = "/api/v1"


@pytest.fixture
def cliente(client, dueno):
    client.force_login(dueno)
    return client


def _post(c, url, datos=None):
    return c.post(f"{API}{url}", datos or {}, content_type="application/json")


def _patch(c, url, datos):
    return c.patch(f"{API}{url}", datos, content_type="application/json")


# --- acceso -------------------------------------------------------------------------------------


def test_sin_sesion_no_hay_datos(client):
    assert client.get(f"{API}/pizarras/").status_code == 403


def test_entrar_salir_y_yo(client, crear_usuario):
    crear_usuario("ana@ejemplo.mx")
    r = _post(
        client, "/auth/entrar/", {"correo": "ANA@ejemplo.mx", "password": "contraseña-de-prueba"}
    )
    assert r.status_code == 200 and r.json()["correo"] == "ana@ejemplo.mx"
    assert client.get(f"{API}/yo/").status_code == 200
    _post(client, "/auth/salir/")
    assert client.get(f"{API}/yo/").status_code == 403


def test_entrar_con_contraseña_mala(client, crear_usuario):
    crear_usuario("ana@ejemplo.mx")
    r = _post(client, "/auth/entrar/", {"correo": "ana@ejemplo.mx", "password": "otra"})
    assert r.status_code == 400 and "incorrectos" in r.json()["detalle"]


def test_entrar_exige_csrf(crear_usuario):
    crear_usuario("ana@ejemplo.mx")
    c = Client(enforce_csrf_checks=True)
    r = _post(c, "/auth/entrar/", {"correo": "ana@ejemplo.mx", "password": "contraseña-de-prueba"})
    assert r.status_code == 403
    c.get(f"{API}/auth/csrf/")
    token = c.cookies["taskflow_csrftoken"].value
    r = c.post(
        f"{API}/auth/entrar/",
        {"correo": "ana@ejemplo.mx", "password": "contraseña-de-prueba"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert r.status_code == 200


# El código sale con transaction.on_commit: estas pruebas necesitan transacciones reales.
CORREO_REAL = pytest.mark.django_db(transaction=True)


def _codigo(mailoutbox):
    """El código de 6 dígitos del último correo enviado."""
    return re.search(r"\b(\d{6})\b", mailoutbox[-1].body).group(1)


DATOS_REGISTRO = {
    "nombre": "Sofía",
    "primer_apellido": "Méndez",
    "segundo_apellido": "Ruiz",
    "correo": "sofia@ejemplo.mx",
    "password": "una-clave-larga-9",
}


@CORREO_REAL
def test_registro_pide_codigo_y_entra_al_verificar(client, mailoutbox):
    r = _post(client, "/auth/registro/", DATOS_REGISTRO)
    assert r.status_code == 201 and r.json() == {"verificar": True, "correo": "sofia@ejemplo.mx"}
    assert client.get(f"{API}/yo/").status_code == 403  # Sin sesión hasta confirmar el correo.
    assert len(mailoutbox) == 1 and mailoutbox[0].to == ["sofia@ejemplo.mx"]
    r = _post(client, "/auth/verificar/", {"correo": "sofia@ejemplo.mx", "codigo": "000000"})
    assert r.status_code == 400 and "codigo" in r.json()
    r = _post(
        client, "/auth/verificar/", {"correo": "sofia@ejemplo.mx", "codigo": _codigo(mailoutbox)}
    )
    assert r.status_code == 200
    assert client.get(f"{API}/yo/").json()["nombre"] == "Sofía Méndez Ruiz"


def test_registro_rechaza_correo_repetido_y_registro_cerrado(client, settings):
    assert _post(client, "/auth/registro/", DATOS_REGISTRO).status_code == 201
    r = _post(Client(), "/auth/registro/", DATOS_REGISTRO)
    assert r.status_code == 400 and "correo" in r.json()
    settings.TASKFLOW_REGISTRO_ABIERTO = False
    otra = {**DATOS_REGISTRO, "correo": "otra@ejemplo.mx"}
    assert _post(Client(), "/auth/registro/", otra).status_code == 403


def test_registro_valida_contraseña_y_primer_apellido(client):
    r = _post(
        client, "/auth/registro/", {"nombre": "A", "correo": "a@ejemplo.mx", "password": "123"}
    )
    assert r.status_code == 400 and {"password", "primer_apellido"} <= set(r.json())


@CORREO_REAL
def test_entrar_sin_verificar_manda_codigo(client, crear_usuario, mailoutbox):
    crear_usuario("ana@ejemplo.mx", correo_verificado_en=None)
    datos = {"correo": "ana@ejemplo.mx", "password": "contraseña-de-prueba"}
    r = _post(client, "/auth/entrar/", datos)
    assert r.status_code == 403 and r.json()["verificar"] is True
    assert len(mailoutbox) == 1 and client.get(f"{API}/yo/").status_code == 403
    # Reintentar enseguida no manda otro correo (espera de un minuto entre envíos).
    assert _post(client, "/auth/entrar/", datos).status_code == 403 and len(mailoutbox) == 1


@CORREO_REAL
def test_reenviar_verificacion_respeta_la_espera(client, crear_usuario, mailoutbox):
    crear_usuario("ana@ejemplo.mx", correo_verificado_en=None)
    assert (
        _post(client, "/auth/verificar/reenviar/", {"correo": "ana@ejemplo.mx"}).status_code == 200
    )
    r = _post(client, "/auth/verificar/reenviar/", {"correo": "ana@ejemplo.mx"})
    assert r.status_code == 400 and len(mailoutbox) == 1
    # Un correo sin cuenta responde igual que uno con cuenta.
    assert (
        _post(client, "/auth/verificar/reenviar/", {"correo": "nadie@ejemplo.mx"}).status_code
        == 200
    )


@CORREO_REAL
def test_recuperar_contraseña(client, crear_usuario, mailoutbox):
    crear_usuario("ana@ejemplo.mx")
    assert _post(client, "/auth/recuperar/", {"correo": "nadie@ejemplo.mx"}).json() == {"ok": True}
    assert len(mailoutbox) == 0
    assert _post(client, "/auth/recuperar/", {"correo": "ANA@ejemplo.mx"}).status_code == 200
    datos = {"correo": "ana@ejemplo.mx", "codigo": _codigo(mailoutbox), "password": "123"}
    r = _post(client, "/auth/recuperar/confirmar/", datos)
    assert r.status_code == 400 and "password" in r.json()
    r = _post(client, "/auth/recuperar/confirmar/", {**datos, "password": "otra-clave-larga-7"})
    assert r.status_code == 200 and client.get(f"{API}/yo/").status_code == 200
    # El código ya se usó y la contraseña nueva sirve para entrar.
    assert (
        _post(
            Client(), "/auth/recuperar/confirmar/", {**datos, "password": "x-clave-larga-8"}
        ).status_code
        == 400
    )
    entrar = {"correo": "ana@ejemplo.mx", "password": "otra-clave-larga-7"}
    assert _post(Client(), "/auth/entrar/", entrar).status_code == 200


@CORREO_REAL
def test_recuperar_verifica_el_correo(client, crear_usuario, mailoutbox):
    """Quien no verificó (o alguien registró su correo antes) recupera la cuenta con el código."""
    u = crear_usuario("ana@ejemplo.mx", correo_verificado_en=None)
    _post(client, "/auth/recuperar/", {"correo": "ana@ejemplo.mx"})
    datos = {
        "correo": "ana@ejemplo.mx",
        "codigo": _codigo(mailoutbox),
        "password": "otra-clave-larga-7",
    }
    assert _post(client, "/auth/recuperar/confirmar/", datos).status_code == 200
    u.refresh_from_db()
    assert u.correo_verificado


# --- pizarras -----------------------------------------------------------------------------------


def test_crear_y_listar_pizarras(cliente):
    r = _post(cliente, "/pizarras/", {"nombre": "Feria 2027"})
    assert r.status_code == 201 and r.json()["rol"] == "dueno"
    assert r.json()["permisos"]["eliminar"] is True
    assert r.json()["listas"] == []  # nace vacía: las listas las elige el usuario
    resumen = next(p for p in cliente.get(f"{API}/pizarras/").json() if p["nombre"] == "Feria 2027")
    assert resumen["conteos"] == {"tarjetas": 0, "listas": 0, "mias": 0, "vencidas": 0}


def test_pizarra_ajena_es_404(pizarra, listas, client, crear_usuario):
    client.force_login(crear_usuario())
    assert client.get(f"{API}/pizarras/{pizarra.pk}/").status_code == 404
    assert client.get(f"{API}/pizarras/{pizarra.pk}/tarjetas/").status_code == 404
    assert _post(client, f"/pizarras/{pizarra.pk}/listas/", {"nombre": "x"}).status_code == 404
    assert _post(client, f"/pizarras/{pizarra.pk}/listas/orden/", {"ids": []}).status_code == 404
    lista = listas["Pendiente"].pk
    assert _patch(client, f"/listas/{lista}/", {"nombre": "x"}).status_code == 404
    assert client.delete(f"{API}/listas/{lista}/").status_code == 404


def test_miembro_ve_su_rol_y_permisos(pizarra, client, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    client.force_login(luis)
    d = client.get(f"{API}/pizarras/{pizarra.pk}/").json()
    assert d["rol"] == "miembro" and d["permisos"]["crear"] and d["permisos"]["mover"]
    assert not d["permisos"]["eliminar"] and not d["permisos"]["gestionar_listas"]
    assert d["invitaciones"] == []  # solo el dueño las ve


def test_acciones_del_dueno(cliente, pizarra, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    r = _patch(cliente, f"/pizarras/{pizarra.pk}/miembros/{luis.pk}/", {"gestionar_listas": True})
    assert r.status_code == 200
    luis_d = next(m for m in r.json()["miembros"] if m["usuario"]["id"] == luis.pk)
    assert luis_d["permisos"]["gestionar_listas"] is True
    assert _post(cliente, f"/pizarras/{pizarra.pk}/archivar/").json()["archivada"] is True
    assert _post(cliente, f"/pizarras/{pizarra.pk}/restaurar/").json()["archivada"] is False
    r = _post(cliente, f"/pizarras/{pizarra.pk}/transferir/", {"usuario": luis.pk})
    assert r.status_code == 200 and r.json()["rol"] == "miembro"


def test_miembro_no_hace_acciones_de_dueno(pizarra, client, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    client.force_login(luis)
    assert _post(client, f"/pizarras/{pizarra.pk}/archivar/").status_code == 403
    assert (
        _post(
            client, f"/pizarras/{pizarra.pk}/invitaciones/", {"correo": "x@ejemplo.mx"}
        ).status_code
        == 403
    )
    assert client.delete(f"{API}/pizarras/{pizarra.pk}/").status_code == 403


def test_conteos_de_mis_pizarras(cliente, pizarra, dueno, listas):
    st.crear_tarjeta(pizarra, dueno, titulo="mía", asignados=[dueno])
    vieja = datetime.date(2020, 1, 1)
    st.crear_tarjeta(pizarra, dueno, titulo="vencida", fecha_inicio=vieja, fecha_fin=vieja)
    # Sin listas de cierre (2026-10-06): con la fecha pasada sale vencida esté donde esté.
    st.crear_tarjeta(
        pizarra,
        dueno,
        titulo="en Finalizada",
        lista=listas["Finalizada"],
        fecha_inicio=vieja,
        fecha_fin=vieja,
    )
    (p,) = cliente.get(f"{API}/pizarras/").json()
    assert p["conteos"] == {"tarjetas": 3, "listas": 3, "mias": 1, "vencidas": 2}


# --- listas -------------------------------------------------------------------------------------


def test_listas_crear_renombrar_ordenar_y_eliminar(cliente, pizarra, listas):
    r = _post(cliente, f"/pizarras/{pizarra.pk}/listas/", {"nombre": "Ideas"})
    assert r.status_code == 201
    ideas = next(lst for lst in r.json()["listas"] if lst["nombre"] == "Ideas")
    r = _post(cliente, f"/pizarras/{pizarra.pk}/listas/", {"nombre": "ideas"})
    assert r.status_code == 400 and "nombre" in r.json()
    r = _patch(cliente, f"/listas/{ideas['id']}/", {"nombre": "Lluvia de ideas"})
    cambiada = next(lst for lst in r.json()["listas"] if lst["id"] == ideas["id"])
    assert cambiada == {**cambiada, "nombre": "Lluvia de ideas"} and "es_cierre" not in cambiada
    ids = [ideas["id"], *(lst.pk for lst in listas.values())]
    r = _post(cliente, f"/pizarras/{pizarra.pk}/listas/orden/", {"ids": ids})
    assert [lst["id"] for lst in r.json()["listas"]] == ids
    assert cliente.delete(f"{API}/listas/{ideas['id']}/").status_code == 200


def test_lista_con_tarjetas_no_se_elimina(cliente, pizarra, dueno, listas):
    st.crear_tarjeta(pizarra, dueno, titulo="a")
    r = cliente.delete(f"{API}/listas/{listas['Pendiente'].pk}/")
    assert r.status_code == 400 and "muévelas" in r.json()["detalle"]


def test_gestionar_listas_sin_permiso_es_403(
    pizarra, listas, client, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    client.force_login(luis)
    assert _post(client, f"/pizarras/{pizarra.pk}/listas/", {"nombre": "x"}).status_code == 403
    assert _patch(client, f"/listas/{listas['Pendiente'].pk}/", {"nombre": "x"}).status_code == 403


# --- invitaciones -------------------------------------------------------------------------------


def test_flujo_de_invitacion_con_registro(
    cliente, pizarra, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        r = _post(cliente, f"/pizarras/{pizarra.pk}/invitaciones/", {"correo": "sofia@ejemplo.mx"})
    assert r.status_code == 201 and len(mailoutbox) == 1
    inv = r.json()["invitaciones"][0]
    token = pizarra.invitaciones.get(pk=inv["id"]).token
    anonimo = Client()
    info = anonimo.get(f"{API}/invitaciones/{token}/").json()
    assert info["pizarra"] == pizarra.nombre and info["existe_cuenta"] is False
    r = _post(
        anonimo,
        f"/invitaciones/{token}/registro/",
        {"nombre": "Sofía", "primer_apellido": "Méndez", "password": "una-clave-larga-9"},
    )
    assert r.status_code == 201 and r.json()["pizarra"] == pizarra.pk
    # El enlace llegó a su correo: entra sin código.
    assert len(mailoutbox) == 1 and r.json()["usuario"]["correo"] == "sofia@ejemplo.mx"
    assert anonimo.get(f"{API}/pizarras/{pizarra.pk}/").status_code == 200


def test_aceptar_invitacion_con_cuenta(pizarra, dueno, client, crear_usuario):
    inv = sp.invitar(pizarra, dueno, "luis@ejemplo.mx")
    client.force_login(crear_usuario("luis@ejemplo.mx"))
    r = _post(client, f"/invitaciones/{inv.token}/aceptar/")
    assert r.status_code == 200 and r.json() == {"pizarra": pizarra.pk}
    client.force_login(crear_usuario("otro@ejemplo.mx"))
    inv2 = sp.invitar(pizarra, dueno, "maria@ejemplo.mx")
    assert _post(client, f"/invitaciones/{inv2.token}/aceptar/").status_code == 403


def test_reenviar_y_cancelar(cliente, pizarra, dueno):
    inv = sp.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    url = f"/pizarras/{pizarra.pk}/invitaciones/{inv.pk}"
    assert _post(cliente, f"{url}/reenviar/").json()["invitaciones"][0]["veces_enviada"] == 2
    assert _post(cliente, f"{url}/cancelar/").json()["invitaciones"] == []


# --- tipos y tarjetas ---------------------------------------------------------------------------


def test_tipos(cliente, pizarra):
    r = _post(cliente, f"/pizarras/{pizarra.pk}/tipos/", {"nombre": "Diseño", "color": "#EC4899"})
    assert r.status_code == 201 and r.json()["color"] == "#ec4899"
    tid = r.json()["id"]
    assert (
        _patch(cliente, f"/pizarras/{pizarra.pk}/tipos/{tid}/", {"color": "#6366f1"}).json()[
            "color"
        ]
        == "#6366f1"
    )
    r = _post(cliente, f"/pizarras/{pizarra.pk}/tipos/", {"nombre": "diseño", "color": "#000000"})
    assert r.status_code == 400 and "nombre" in r.json()
    assert cliente.delete(f"{API}/pizarras/{pizarra.pk}/tipos/{tid}/").status_code == 204


def test_ciclo_de_una_tarjeta(cliente, pizarra, dueno, listas):
    tipo = sp.crear_tipo(pizarra, dueno, nombre="Logística", color="#0ea5e9")
    r = _post(
        cliente,
        f"/pizarras/{pizarra.pk}/tarjetas/",
        {
            "titulo": "Auditorio",
            "lista": listas["En curso"].pk,
            "prioridad": "urgente",
            "fecha_inicio": "2026-10-01",
            "fecha_fin": "2026-10-20",
            "asignados": [dueno.pk],
            "tipos": [tipo.pk],
        },
    )
    assert r.status_code == 201, r.json()
    t = r.json()
    assert (t["descripcion"], t["lista_nombre"], t["lista_terminado"]) == ("", "En curso", None)
    assert (t["fecha_inicio"], t["fecha_fin"], t["tipos"]) == (
        "2026-10-01",
        "2026-10-20",
        [tipo.pk],
    )
    assert t["historial"] == [
        {**t["historial"][0], "de": None, "a": "En curso", "nota": None},
    ]
    r = _post(cliente, f"/tarjetas/{t['id']}/mover/", {"lista": listas["Finalizada"].pk})
    assert r.json()["lista_nombre"] == "Finalizada"
    assert len(r.json()["historial"]) == 2
    r = _patch(cliente, f"/tarjetas/{t['id']}/", {"titulo": "Auditorio central", "fecha_fin": None})
    assert r.json()["titulo"] == "Auditorio central" and r.json()["fecha_fin"] is None
    assert _patch(cliente, f"/tarjetas/{t['id']}/", {"fecha_fin": "mañana"}).status_code == 400
    r = _patch(cliente, f"/tarjetas/{t['id']}/", {"fecha_fin": "2026-09-01"})
    assert r.status_code == 400 and "fecha_fin" in r.json()
    assert cliente.delete(f"{API}/tarjetas/{t['id']}/").status_code == 204


def test_tablero_en_orden_de_lista_y_posicion(cliente, pizarra, dueno, listas):
    for titulo, lista in [("b", "En curso"), ("p1", "Pendiente"), ("p2", "Pendiente")]:
        st.crear_tarjeta(pizarra, dueno, titulo=titulo, lista=listas[lista])
    p2 = Tarjeta.objects.get(titulo="p2")
    _post(cliente, f"/tarjetas/{p2.pk}/mover/", {"lista": listas["Pendiente"].pk, "posicion": 0})
    titulos = [t["titulo"] for t in cliente.get(f"{API}/pizarras/{pizarra.pk}/tarjetas/").json()]
    assert titulos == ["p2", "p1", "b"]


def test_tarjeta_ajena_es_404_y_sin_permiso_es_403(
    pizarra, dueno, client, crear_usuario, agregar_miembro, listas
):
    t = st.crear_tarjeta(pizarra, dueno, titulo="a")
    e = st.agregar_elemento(t, dueno, "paso")
    client.force_login(crear_usuario())
    assert client.get(f"{API}/tarjetas/{t.pk}/").status_code == 404
    assert (
        _post(client, f"/tarjetas/{t.pk}/mover/", {"lista": listas["En curso"].pk}).status_code
        == 404
    )
    assert _post(client, f"/tarjetas/{t.pk}/checklist/", {"texto": "x"}).status_code == 404
    assert _post(client, f"/tarjetas/{t.pk}/checklist/orden/", {"ids": [e.pk]}).status_code == 404
    assert _patch(client, f"/checklist/{e.pk}/", {"hecho": True}).status_code == 404
    assert client.delete(f"{API}/checklist/{e.pk}/").status_code == 404
    assert _post(client, f"/checklist/{e.pk}/convertir/").status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, mover=False, editar=False, crear=False)
    client.force_login(luis)
    r = _post(client, f"/tarjetas/{t.pk}/mover/", {"lista": listas["En curso"].pk})
    assert r.status_code == 403 and "permiso" in r.json()["detalle"]
    assert _post(client, f"/tarjetas/{t.pk}/checklist/", {"texto": "x"}).status_code == 403
    assert _patch(client, f"/checklist/{e.pk}/", {"hecho": True}).status_code == 403
    assert _post(client, f"/checklist/{e.pk}/convertir/").status_code == 403


def test_mover_a_lista_de_otra_pizarra_es_400(cliente, pizarra, dueno):
    t = st.crear_tarjeta(pizarra, dueno, titulo="a")
    otra = sp.crear_pizarra(dueno, "Otra")
    ajena = sp.crear_lista(otra, dueno, "Pendiente")
    r = _post(cliente, f"/tarjetas/{t.pk}/mover/", {"lista": ajena.pk})
    assert r.status_code == 400 and "lista" in r.json()


def test_mis_tarjetas_son_las_asignadas_en_cualquier_lista(cliente, pizarra, dueno, listas):
    st.crear_tarjeta(pizarra, dueno, titulo="mía", asignados=[dueno])
    st.crear_tarjeta(pizarra, dueno, titulo="de nadie")
    otra = st.crear_tarjeta(pizarra, dueno, titulo="otra mía", asignados=[dueno])
    st.mover_tarjeta(otra, dueno, listas["Finalizada"])  # ninguna lista la saca (2026-10-06)
    titulos = {t["titulo"] for t in cliente.get(f"{API}/yo/tarjetas/").json()}
    assert titulos == {"mía", "otra mía"}


# --- checklist ----------------------------------------------------------------------------------


def test_checklist_y_conversion_enlazada(cliente, pizarra, dueno, listas):
    t = st.crear_tarjeta(pizarra, dueno, titulo="Programa")
    r = _post(cliente, f"/tarjetas/{t.pk}/checklist/", {"texto": "Asignar salas"})
    assert r.status_code == 201
    _post(cliente, f"/tarjetas/{t.pk}/checklist/", {"texto": "Imprimir"})
    salas, imprimir = (e["id"] for e in cliente.get(f"{API}/tarjetas/{t.pk}/").json()["checklist"])
    r = _patch(cliente, f"/checklist/{imprimir}/", {"hecho": True})
    assert r.json()["checklist_conteo"] == {"hechos": 1, "total": 2}
    r = _post(cliente, f"/checklist/{salas}/convertir/", {"prioridad": "alta"})
    assert r.status_code == 201
    padre, nueva = r.json()["tarjeta"], r.json()["nueva"]
    elemento = next(e for e in padre["checklist"] if e["id"] == salas)
    assert elemento["tarjeta"] == {
        "id": nueva["id"],
        "titulo": "Asignar salas",
        "lista": listas["Pendiente"].pk,
        "lista_nombre": "Pendiente",
    }
    assert padre["lista_terminado"] is None and not elemento["automatico"]
    assert nueva["viene_de"] == {"id": t.pk, "titulo": "Programa", "elemento": "Asignar salas"}
    # «Lo que llega a En curso cuenta como terminado», para toda la checklist; no la propia.
    r = _patch(cliente, f"/tarjetas/{t.pk}/", {"lista_terminado": listas["Pendiente"].pk})
    assert r.status_code == 400 and "lista_terminado" in r.json()
    r = _patch(cliente, f"/tarjetas/{t.pk}/", {"lista_terminado": listas["En curso"].pk})
    assert r.json()["lista_terminado"] == listas["En curso"].pk
    _post(cliente, f"/tarjetas/{nueva['id']}/mover/", {"lista": listas["En curso"].pk})
    padre = cliente.get(f"{API}/tarjetas/{t.pk}/").json()
    assert padre["checklist_conteo"] == {"hechos": 2, "total": 2}
    assert _patch(cliente, f"/checklist/{salas}/", {"hecho": False}).status_code == 400
    # A palomeo manual, conservando el estado.
    r = _patch(cliente, f"/tarjetas/{t.pk}/", {"lista_terminado": None})
    elemento = next(e for e in r.json()["checklist"] if e["id"] == salas)
    assert elemento["hecho"] is True and elemento["automatico"] is False
    r = _post(cliente, f"/tarjetas/{t.pk}/checklist/orden/", {"ids": [imprimir, salas]})
    assert [e["id"] for e in r.json()["checklist"]] == [imprimir, salas]
    assert cliente.delete(f"{API}/checklist/{imprimir}/").status_code == 200


def test_convertir_usa_la_lista_de_terminado_de_la_tarjeta(cliente, pizarra, dueno, listas):
    t = st.crear_tarjeta(pizarra, dueno, titulo="Programa")
    st.editar_tarjeta(t, dueno, lista_terminado=listas["Finalizada"].pk)
    e = st.agregar_elemento(t, dueno, "Imprimir")
    r = _post(cliente, f"/checklist/{e.pk}/convertir/")
    elemento = r.json()["tarjeta"]["checklist"][0]
    assert elemento["automatico"] and not elemento["hecho"]
    r = _post(cliente, f"/checklist/{e.pk}/convertir/")
    assert r.status_code == 400  # ya convertido


# --- cuenta, portada y PWA ----------------------------------------------------------------------


def test_cambiar_contraseña(cliente):
    r = _post(cliente, "/yo/password/", {"actual": "mala", "nueva": "otra-clave-larga-9"})
    assert r.status_code == 400 and "actual" in r.json()
    r = _post(
        cliente, "/yo/password/", {"actual": "contraseña-de-prueba", "nueva": "otra-clave-larga-9"}
    )
    assert r.status_code == 200
    assert cliente.get(f"{API}/yo/").status_code == 200  # la sesión sigue viva


def test_portada_y_pwa_sin_compilar(client, settings, tmp_path):
    assert client.get("/").status_code == 200
    settings.PWA_DIR = tmp_path
    assert client.get("/app/").status_code == 503


def test_csrf_trae_el_usuario_de_la_sesion(client, crear_usuario):
    assert client.get(f"{API}/auth/csrf/").json()["usuario"] is None
    client.force_login(crear_usuario("ana@ejemplo.mx"))
    assert client.get(f"{API}/auth/csrf/").json()["usuario"]["correo"] == "ana@ejemplo.mx"


def test_yo_trae_nombre_y_apellidos_por_separado(client, crear_usuario):
    u = crear_usuario("ana@ejemplo.mx", nombre="Ana", primer_apellido="López")
    client.force_login(u)
    datos = client.get(f"{API}/yo/").json()
    assert datos["nombre"] == "Ana López"
    assert (datos["nombre_pila"], datos["primer_apellido"], datos["segundo_apellido"]) == (
        "Ana",
        "López",
        "",
    )
    r = _patch(client, "/yo/", {"segundo_apellido": "Ramírez"})
    assert r.json()["nombre"] == "Ana López Ramírez"
    r = _patch(client, "/yo/", {"primer_apellido": " "})
    assert r.status_code == 400 and "primer_apellido" in r.json()
