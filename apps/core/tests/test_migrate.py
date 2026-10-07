"""Paso previo de `migrate`: una base con una etiqueta vieja pasa a la nueva (§11).

`proyectos` → `pizarras` (2026-10-05, tablas explícitas) y `tarjetas` → `actividades`
(2026-10-06, por prefijo).
"""

import pytest
from django.db import connection
from django.utils import timezone

from apps.core.management.commands.migrate import renombrar_etiqueta


def _sembrar(etiqueta, tabla):
    with connection.cursor() as c:
        c.execute(f"CREATE TABLE {tabla} (id integer)")
        c.execute(
            "INSERT INTO django_migrations (app, name, applied) VALUES (%s, %s, %s)",
            [etiqueta, "0001_prueba", timezone.now()],
        )
        c.execute(
            "INSERT INTO django_content_type (app_label, model) VALUES (%s, %s)",
            [etiqueta, "prueba"],
        )


def _comprobar(nueva):
    with connection.cursor() as c:
        c.execute("SELECT app FROM django_migrations WHERE name = %s", ["0001_prueba"])
        assert c.fetchone()[0] == nueva
        c.execute("SELECT app_label FROM django_content_type WHERE model = %s", ["prueba"])
        assert c.fetchone()[0] == nueva


def _limpiar(*tablas):
    with connection.cursor() as c:
        for t in tablas:
            c.execute(f"DROP TABLE IF EXISTS {t}")
        c.execute("DELETE FROM django_migrations WHERE name = %s", ["0001_prueba"])
        c.execute("DELETE FROM django_content_type WHERE model = %s", ["prueba"])


@pytest.mark.django_db(transaction=True)
def test_pasa_tablas_historial_y_tipos_de_contenido():
    tablas = {"proyectos_prueba": "pizarras_prueba"}
    _sembrar("proyectos", "proyectos_prueba")
    try:
        assert renombrar_etiqueta(connection, "proyectos", "pizarras", tablas)
        existentes = connection.introspection.table_names()
        assert "pizarras_prueba" in existentes and "proyectos_prueba" not in existentes
        _comprobar("pizarras")
        # Ya pasada (o base nueva): no hace nada.
        assert not renombrar_etiqueta(connection, "proyectos", "pizarras", tablas)
    finally:
        _limpiar("pizarras_prueba", "proyectos_prueba")


@pytest.mark.django_db(transaction=True)
def test_sin_lista_de_tablas_pasa_todas_las_del_prefijo():
    _sembrar("tarjetas", "tarjetas_prueba")
    try:
        assert renombrar_etiqueta(connection, "tarjetas", "actividades")
        existentes = connection.introspection.table_names()
        assert "actividades_prueba" in existentes and "tarjetas_prueba" not in existentes
        _comprobar("actividades")
        assert not renombrar_etiqueta(connection, "tarjetas", "actividades")
    finally:
        _limpiar("actividades_prueba", "tarjetas_prueba")
