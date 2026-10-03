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


def test_portada_muestra_el_dominio_desde_el_que_se_abre(client, db):
    """La dirección de instalación sale de la petición, no de un dominio escrito en la plantilla."""
    html = client.get("/", HTTP_HOST="taskflow.ejemplo.mx").content.decode()
    assert "<b>taskflow.ejemplo.mx</b>" in html
    assert "reduaz" not in html
