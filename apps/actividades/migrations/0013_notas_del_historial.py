"""
Etapa 3.8 (2026-10-06): las notas del historial que dejó `convertir_elemento` decían «…de la
checklist en tarjeta»; pasan a «…en actividad». Aparte de `0012` por la restricción de PostgreSQL
descrita ahí. Reversible.
"""

from django.db import migrations

# Las notas del historial que escribía `convertir_elemento`; las demás no dicen «tarjeta».
NOTA_VIEJA = " de la checklist en tarjeta"
NOTA_NUEVA = " de la checklist en actividad"


def _reescribir_notas(apps, de, a):
    Movimiento = apps.get_model("actividades", "Movimiento")
    cambiadas = []
    for m in Movimiento.objects.filter(nota__endswith=de):
        m.nota = m.nota[: -len(de)] + a
        cambiadas.append(m)
    Movimiento.objects.bulk_update(cambiadas, ["nota"])


def notas_a_actividad(apps, schema_editor):
    _reescribir_notas(apps, NOTA_VIEJA, NOTA_NUEVA)


def notas_a_tarjeta(apps, schema_editor):
    _reescribir_notas(apps, NOTA_NUEVA, NOTA_VIEJA)


class Migration(migrations.Migration):
    dependencies = [("actividades", "0012_tarjeta_a_actividad")]

    operations = [migrations.RunPython(notas_a_actividad, notas_a_tarjeta)]
