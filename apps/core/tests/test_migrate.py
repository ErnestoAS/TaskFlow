"""Paso previo de `migrate`: una base con la app `proyectos` pasa a `pizarras` (2026-10-05)."""

import pytest
from django.db import connection
from django.utils import timezone

from apps.core.management.commands.migrate import renombrar_etiqueta

TABLAS = {"proyectos_prueba": "pizarras_prueba"}


@pytest.mark.django_db(transaction=True)
def test_pasa_tablas_historial_y_tipos_de_contenido():
    with connection.cursor() as c:
        c.execute("CREATE TABLE proyectos_prueba (id integer)")
        c.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
            ["proyectos", "0001_prueba", timezone.now()],
        )
        c.execute(
            "INSERT INTO django_content_type (app_label, model) VALUES (%s, %s)",
            ["proyectos", "prueba"],
        )
    try:
        assert renombrar_etiqueta(connection, tablas=TABLAS)
        tablas = connection.introspection.table_names()
        assert "pizarras_prueba" in tablas and "proyectos_prueba" not in tablas
        with connection.cursor() as c:
            c.execute("SELECT app FROM django_migrations WHERE name = %s", ["0001_prueba"])
            assert c.fetchone()[0] == "pizarras"
            c.execute("SELECT app_label FROM django_content_type WHERE model = %s", ["prueba"])
            assert c.fetchone()[0] == "pizarras"
        # Ya pasada (o base nueva): no hace nada.
        assert not renombrar_etiqueta(connection, tablas=TABLAS)
    finally:
        with connection.cursor() as c:
            c.execute("DROP TABLE IF EXISTS pizarras_prueba")
            c.execute("DROP TABLE IF EXISTS proyectos_prueba")
            c.execute("DELETE FROM django_migrations WHERE name = %s", ["0001_prueba"])
