def test_healthz(client, db):
    respuesta = client.get("/healthz/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_healthz_bajo_prefijo(client, db):
    """En producción la app vive en /taskflow/: healthz debe responder igual con el prefijo."""
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
