"""
Historial de la pizarra (2026-10-20, §5): `Movimiento` guarda su pizarra y el título de la
actividad, y deja de borrarse con la actividad (`SET_NULL`), para que el historial de la pizarra
diga quién eliminó qué. Rellena `pizarra` y `titulo` en las filas que ya había.

Reversible: al regresar se borran las filas que ya no tienen actividad (las de actividades
eliminadas después de esta migración), porque antes `actividad` era obligatoria.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def rellenar(apps, schema_editor):
    Movimiento = apps.get_model("actividades", "Movimiento")
    Actividad = apps.get_model("actividades", "Actividad")
    suya = Actividad.objects.filter(pk=OuterRef("actividad_id"))
    Movimiento.objects.update(
        pizarra_id=Subquery(suya.values("pizarra_id")[:1]),
        titulo=Subquery(suya.values("titulo")[:1]),
    )


def borrar_huerfanos(apps, schema_editor):
    apps.get_model("actividades", "Movimiento").objects.filter(actividad__isnull=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("actividades", "0019_comentarios"),
        ("pizarras", "0007_solicitantes"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimiento",
            name="pizarra",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="movimientos",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AddField(
            model_name="movimiento",
            name="titulo",
            field=models.CharField(
                blank=True, default="", max_length=200, verbose_name="título de la actividad"
            ),
            preserve_default=False,
        ),
        migrations.RunPython(rellenar, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="movimiento",
            name="pizarra",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="movimientos",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AlterField(
            model_name="movimiento",
            name="actividad",
            field=models.ForeignKey(
                blank=True,
                help_text=(
                    "Vacía si la actividad se eliminó: su historial se queda en el de la pizarra."
                ),
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="movimientos",
                to="actividades.actividad",
                verbose_name="actividad",
            ),
        ),
        migrations.AddIndex(
            model_name="movimiento",
            index=models.Index(fields=["pizarra", "-fecha"], name="movimiento_pizarra_fecha"),
        ),
        # Al regresar corre primero: sin esto, volver `actividad` a obligatoria fallaría.
        migrations.RunPython(migrations.RunPython.noop, borrar_huerfanos),
    ]
