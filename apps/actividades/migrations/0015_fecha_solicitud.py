"""
Etapa 3.8 (2026-10-06, §4.7 de la propuesta): `fecha_inicio` pasa a `fecha_solicitud` («Solicitada
el»), opcional y sin valor por omisión, y `fecha_fin` se muestra como «Vence el». Las fechas que ya
había se conservan. La restricción de orden deja pasar una fecha de solicitud vacía.

A mano porque `makemigrations` no detecta renombres sin preguntar. Al revertir, las vacías toman la
fecha de captura (`creado_en`, en hora de México), como hacía `0008` al crear el campo.
"""

from django.db import migrations, models
from django.db.models import F, Q
from django.utils import timezone


def vacias_a_captura(apps, schema_editor):
    Actividad = apps.get_model("actividades", "Actividad")
    vacias = list(Actividad.objects.filter(fecha_solicitud__isnull=True))
    for a in vacias:
        a.fecha_solicitud = timezone.localdate(a.creado_en)
        if a.fecha_fin and a.fecha_fin < a.fecha_solicitud:
            a.fecha_solicitud = a.fecha_fin
    Actividad.objects.bulk_update(vacias, ["fecha_solicitud"])


class Migration(migrations.Migration):
    dependencies = [("actividades", "0014_nombres_de_actividad")]

    operations = [
        migrations.RemoveConstraint(model_name="actividad", name="actividad_fechas_en_orden"),
        migrations.RenameField("actividad", "fecha_inicio", "fecha_solicitud"),
        migrations.AlterField(
            model_name="actividad",
            name="fecha_solicitud",
            field=models.DateField(blank=True, null=True, verbose_name="solicitada el"),
        ),
        migrations.AlterField(
            model_name="actividad",
            name="fecha_fin",
            field=models.DateField(blank=True, null=True, verbose_name="vence el"),
        ),
        migrations.AddConstraint(
            model_name="actividad",
            constraint=models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True)
                | Q(fecha_solicitud__isnull=True)
                | Q(fecha_fin__gte=F("fecha_solicitud")),
                name="actividad_fechas_en_orden",
            ),
        ),
        # Solo hace algo al revertir: el campo vuelve a ser obligatorio.
        migrations.RunPython(migrations.RunPython.noop, vacias_a_captura),
    ]
