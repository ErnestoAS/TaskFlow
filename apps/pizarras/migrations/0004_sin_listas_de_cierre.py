"""
Fuera las listas de cierre (2026-10-06, §4.6): ninguna lista significa «terminado» por sí misma.
Depende de `tarjetas.0011` porque `tarjetas.0008` todavía lee `es_cierre` en una base nueva.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("pizarras", "0003_listas_y_permisos"),
        ("tarjetas", "0011_sin_lista_terminado_en_elemento"),
    ]

    operations = [
        migrations.RemoveField(model_name="lista", name="es_cierre"),
    ]
