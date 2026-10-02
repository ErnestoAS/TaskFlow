import re

import pytest
from django.test import Client

from apps.proyectos import servicios as sp
from apps.tarjetas import servicios as st

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
    assert client.get(f"{API}/proyectos/").status_code == 403


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


# --- proyectos ----------------------------------------------------------------------------------


def test_crear_y_listar_proyectos(cliente):
    r = _post(cliente, "/proyectos/", {"nombre": "Feria 2027"})
    assert r.status_code == 201 and r.json()["rol"] == "dueno"
    assert r.json()["permisos"]["eliminar"] is True
    nombres = [p["nombre"] for p in cliente.get(f"{API}/proyectos/").json()]
    assert "Feria 2027" in nombres


def test_proyecto_ajeno_es_404(proyecto, client, crear_usuario):
    client.force_login(crear_usuario())
    assert client.get(f"{API}/proyectos/{proyecto.pk}/").status_code == 404
    assert client.get(f"{API}/proyectos/{proyecto.pk}/tarjetas/").status_code == 404


def test_miembro_ve_su_rol_y_permisos(proyecto, client, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    client.force_login(luis)
    d = client.get(f"{API}/proyectos/{proyecto.pk}/").json()
    assert d["rol"] == "miembro" and d["permisos"]["crear"] and not d["permisos"]["eliminar"]
    assert d["invitaciones"] == []  # solo el dueño las ve


def test_acciones_del_dueno(cliente, proyecto, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    r = _patch(cliente, f"/proyectos/{proyecto.pk}/miembros/{luis.pk}/", {"eliminar": True})
    assert r.status_code == 200
    luis_d = next(m for m in r.json()["miembros"] if m["usuario"]["id"] == luis.pk)
    assert luis_d["permisos"]["eliminar"] is True
    assert _post(cliente, f"/proyectos/{proyecto.pk}/archivar/").json()["archivado"] is True
    assert _post(cliente, f"/proyectos/{proyecto.pk}/restaurar/").json()["archivado"] is False
    r = _post(cliente, f"/proyectos/{proyecto.pk}/transferir/", {"usuario": luis.pk})
    assert r.status_code == 200 and r.json()["rol"] == "miembro"


def test_miembro_no_hace_acciones_de_dueno(proyecto, client, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    client.force_login(luis)
    assert _post(client, f"/proyectos/{proyecto.pk}/archivar/").status_code == 403
    assert (
        _post(
            client, f"/proyectos/{proyecto.pk}/invitaciones/", {"correo": "x@ejemplo.mx"}
        ).status_code
        == 403
    )
    assert client.delete(f"{API}/proyectos/{proyecto.pk}/").status_code == 403


# --- invitaciones -------------------------------------------------------------------------------


def test_flujo_de_invitacion_con_registro(
    cliente, proyecto, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        r = _post(
            cliente, f"/proyectos/{proyecto.pk}/invitaciones/", {"correo": "sofia@ejemplo.mx"}
        )
    assert r.status_code == 201 and len(mailoutbox) == 1
    inv = r.json()["invitaciones"][0]
    token = proyecto.invitaciones.get(pk=inv["id"]).token
    anonimo = Client()
    info = anonimo.get(f"{API}/invitaciones/{token}/").json()
    assert info["proyecto"] == proyecto.nombre and info["existe_cuenta"] is False
    r = _post(
        anonimo,
        f"/invitaciones/{token}/registro/",
        {"nombre": "Sofía", "primer_apellido": "Méndez", "password": "una-clave-larga-9"},
    )
    assert r.status_code == 201 and r.json()["proyecto"] == proyecto.pk
    # El enlace llegó a su correo: entra sin código.
    assert len(mailoutbox) == 1 and r.json()["usuario"]["correo"] == "sofia@ejemplo.mx"
    assert anonimo.get(f"{API}/proyectos/{proyecto.pk}/").status_code == 200


def test_aceptar_invitacion_con_cuenta(proyecto, dueno, client, crear_usuario):
    inv = sp.invitar(proyecto, dueno, "luis@ejemplo.mx")
    client.force_login(crear_usuario("luis@ejemplo.mx"))
    assert _post(client, f"/invitaciones/{inv.token}/aceptar/").status_code == 200
    client.force_login(crear_usuario("otro@ejemplo.mx"))
    inv2 = sp.invitar(proyecto, dueno, "maria@ejemplo.mx")
    assert _post(client, f"/invitaciones/{inv2.token}/aceptar/").status_code == 403


def test_reenviar_y_cancelar(cliente, proyecto, dueno):
    inv = sp.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    url = f"/proyectos/{proyecto.pk}/invitaciones/{inv.pk}"
    assert _post(cliente, f"{url}/reenviar/").json()["invitaciones"][0]["veces_enviada"] == 2
    assert _post(cliente, f"{url}/cancelar/").json()["invitaciones"] == []


# --- tipos y tarjetas ---------------------------------------------------------------------------


def test_tipos(cliente, proyecto):
    r = _post(cliente, f"/proyectos/{proyecto.pk}/tipos/", {"nombre": "Diseño", "color": "#EC4899"})
    assert r.status_code == 201 and r.json()["color"] == "#ec4899"
    tid = r.json()["id"]
    assert (
        _patch(cliente, f"/proyectos/{proyecto.pk}/tipos/{tid}/", {"color": "#6366f1"}).json()[
            "color"
        ]
        == "#6366f1"
    )
    r = _post(cliente, f"/proyectos/{proyecto.pk}/tipos/", {"nombre": "diseño", "color": "#000000"})
    assert r.status_code == 400 and "nombre" in r.json()
    assert cliente.delete(f"{API}/proyectos/{proyecto.pk}/tipos/{tid}/").status_code == 204


def test_ciclo_de_una_tarjeta(cliente, proyecto, dueno):
    tipo = sp.crear_tipo(proyecto, dueno, nombre="Logística", color="#0ea5e9")
    r = _post(
        cliente,
        f"/proyectos/{proyecto.pk}/tarjetas/",
        {
            "titulo": "Auditorio",
            "descripcion": "Reservar",
            "prioridad": "urgente",
            "fecha_fin": "2026-10-20",
            "asignados": [dueno.pk],
            "tipos": [tipo.pk],
        },
    )
    assert r.status_code == 201
    t = r.json()
    assert (
        t["prioridad"] == "urgente" and t["fecha_fin"] == "2026-10-20" and t["tipos"] == [tipo.pk]
    )
    assert t["historial"][0]["a"] == "pendiente" and t["historial"][0]["de"] is None
    r = _post(cliente, f"/tarjetas/{t['id']}/estatus/", {"estatus": "finalizada"})
    assert r.json()["estatus"] == "finalizada" and len(r.json()["historial"]) == 2
    r = _patch(cliente, f"/tarjetas/{t['id']}/", {"titulo": "Auditorio central", "fecha_fin": None})
    assert r.json()["titulo"] == "Auditorio central" and r.json()["fecha_fin"] is None
    assert _patch(cliente, f"/tarjetas/{t['id']}/", {"fecha_fin": "mañana"}).status_code == 400
    assert cliente.delete(f"{API}/tarjetas/{t['id']}/").status_code == 204


def test_tablero_ordenado_por_prioridad(cliente, proyecto, dueno):
    for titulo, prioridad in [("b", "baja"), ("u", "urgente"), ("m", "media"), ("a", "alta")]:
        st.crear_tarjeta(proyecto, dueno, titulo=titulo, descripcion="x", prioridad=prioridad)
    titulos = [t["titulo"] for t in cliente.get(f"{API}/proyectos/{proyecto.pk}/tarjetas/").json()]
    assert titulos == ["u", "a", "m", "b"]


def test_tarjeta_ajena_es_404_y_sin_permiso_es_403(
    proyecto, dueno, client, crear_usuario, agregar_miembro
):
    t = st.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    client.force_login(crear_usuario())
    assert client.get(f"{API}/tarjetas/{t.pk}/").status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, cambiar_estatus=False)
    client.force_login(luis)
    r = _post(client, f"/tarjetas/{t.pk}/estatus/", {"estatus": "en_curso"})
    assert r.status_code == 403 and "permiso" in r.json()["detalle"]


def test_mis_tarjetas(cliente, proyecto, dueno):
    st.crear_tarjeta(proyecto, dueno, titulo="mía", descripcion="x", asignados=[dueno])
    st.crear_tarjeta(proyecto, dueno, titulo="de nadie", descripcion="x")
    hecha = st.crear_tarjeta(proyecto, dueno, titulo="hecha", descripcion="x", asignados=[dueno])
    st.cambiar_estatus(hecha, dueno, "finalizada")
    assert [t["titulo"] for t in cliente.get(f"{API}/yo/tarjetas/").json()] == ["mía"]


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
