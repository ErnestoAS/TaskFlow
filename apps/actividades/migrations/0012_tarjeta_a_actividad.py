"""
Etapa 3.8 (2026-10-06, §4.7 de la propuesta): `Tarjeta` pasa a `Actividad` (con sus campos
`tarjeta` y `tarjeta_creada`, restricciones e índices) y se quita la prioridad, con sus datos.

A mano porque `makemigrations` no detecta renombres sin preguntar; los nombres para mostrar y los
`related_name` van en la siguiente. La etiqueta de la app (`tarjetas` → `actividades`) ya la cambió
el `migrate` de `apps.core` antes de llegar aquí. Al revertir, la prioridad vuelve como «media».
Las notas del historial se reescriben en `0013`, aparte: PostgreSQL no deja alterar una tabla en la
misma transacción en que se actualizaron sus filas (al revertir, el orden se invierte).
"""

from django.db import migrations, models
from django.db.models import F, Q

class Migration(migrations.Migration):
    dependencies = [
        ("actividades", "0011_sin_lista_terminado_en_elemento"),
        ("pizarras", "0005_tipotarjeta_a_tipoactividad"),
    ]

    operations = [
        migrations.RemoveConstraint(model_name="tarjeta", name="tarjeta_prioridad_valida"),
        migrations.RemoveField(model_name="tarjeta", name="prioridad"),
        migrations.RemoveConstraint(model_name="tarjeta", name="tarjeta_fechas_en_orden"),
        migrations.RenameIndex(
            model_name="tarjeta",
            new_name="actividad_lista_posicion",
            old_name="tarjeta_lista_posicion",
        ),
        migrations.RenameModel("Tarjeta", "Actividad"),
        migrations.AddConstraint(
            model_name="actividad",
            constraint=models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F("fecha_inicio")),
                name="actividad_fechas_en_orden",
            ),
        ),
        migrations.RemoveIndex(model_name="movimiento", name="movimiento_tarjeta_fecha"),
        migrations.RenameField("movimiento", "tarjeta", "actividad"),
        migrations.AddIndex(
            model_name="movimiento",
            index=models.Index(fields=["actividad", "-fecha"], name="movimiento_actividad_fecha"),
        ),
        migrations.RenameField("elementochecklist", "tarjeta", "actividad"),
        migrations.RenameField("elementochecklist", "tarjeta_creada", "actividad_creada"),
    ]
