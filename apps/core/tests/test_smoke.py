def test_healthz(client, db):
    respuesta = client.get("/healthz/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_healthz_bajo_prefijo(client, db):
    """Si la app se publica bajo una ruta (/taskflow/), healthz debe responder igual."""
    respuesta = client.get("/healthz/", SCRIPT_NAME="/taskflow")
    assert respuesta.status_code == 200


def test_estaticos_con_prefijo(settings):
    """
    Con FORCE_SCRIPT_NAME, STATIC_URL debe llevar el prefijo sin depender de la caché de Django
    (con gunicorn se lee antes de fijarse el prefijo y el admin quedaba sin estilos).
    """
    from django.templatetags.static import static

    settings.STATIC_URL = "/taskflow/static/"
    assert static("admin/css/base.css").startswith("/taskflow/static/")


def test_con_sesion_la_portada_manda_a_la_app(client, crear_usuario):
    """Reporte de un usuario (2026-10-20): con la sesión abierta no tiene caso «Entrar»."""
    assert client.get("/").status_code == 200  # sin sesión, la portada
    client.force_login(crear_usuario())
    r = client.get("/")
    assert r.status_code == 302 and r["Location"] == "/app/"
    # Perfil → «Instalar la app» sí quiere ver la portada.
    assert client.get("/", {"portada": "1"}).status_code == 200
    # Publicada bajo una ruta, la redirección no se sale de ella. El cliente de pruebas no fija el
    # prefijo con SCRIPT_NAME (lo hace el servidor WSGI real), así que se fija a mano.
    from django.urls import clear_script_prefix, set_script_prefix

    set_script_prefix("/taskflow/")
    try:
        assert client.get("/")["Location"] == "/taskflow/app/"
    finally:
        clear_script_prefix()


def test_portada_muestra_el_dominio_desde_el_que_se_abre(client, db):
    """La dirección de instalación sale de la petición, no de un dominio escrito en la plantilla."""
    html = client.get("/", HTTP_HOST="taskflow.ejemplo.mx").content.decode()
    assert "<b>taskflow.ejemplo.mx</b>" in html
    assert "reduaz" not in html
