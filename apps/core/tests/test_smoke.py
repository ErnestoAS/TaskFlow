def test_healthz(client, db):
    respuesta = client.get("/healthz/")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_healthz_bajo_prefijo(client, db):
    """En producción la app vive en /taskflow/: healthz debe responder igual con el prefijo."""
    respuesta = client.get("/healthz/", SCRIPT_NAME="/taskflow")
    assert respuesta.status_code == 200
