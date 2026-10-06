"""
Esquema de la v3 (§4.6), última parte: `lista` y `fecha_inicio` obligatorias, fuera `estatus` y
`CambioEstatus` (ya copiados por `0008`), y las reglas nuevas en la base de datos: índice por
lista y posición, y fecha límite no anterior a la de inicio.
"""

import django.db.models.deletion
from django.db import migrations, models

import apps.tarjetas.models


class Migration(migrations.Migration):
    dependencies = [("tarjetas", "0008_estatus_a_listas")]

    operations = [
        # Solo el texto del campo (renombrado en 0007).
        migrations.AlterField(
            model_name="tarjeta",
            name="pizarra",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tarjetas",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AlterField(
            model_name="tarjeta",
            name="lista",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="tarjetas",
                to="pizarras.lista",
                verbose_name="lista",
            ),
        ),
        migrations.AlterField(
            model_name="tarjeta",
            name="fecha_inicio",
            field=models.DateField(default=apps.tarjetas.models.hoy, verbose_name="fecha de inicio"),
        ),
        migrations.RemoveConstraint(model_name="tarjeta", name="tarjeta_estatus_valido"),
        migrations.RemoveField(model_name="tarjeta", name="estatus"),
        migrations.DeleteModel(name="CambioEstatus"),
        migrations.AddIndex(
            model_name="tarjeta",
            index=models.Index(fields=["lista", "posicion"], name="tarjeta_lista_posicion"),
        ),
        migrations.AddConstraint(
            model_name="tarjeta",
            constraint=models.CheckConstraint(
                condition=models.Q(("fecha_fin__isnull", True))
                | models.Q(("fecha_fin__gte", models.F("fecha_inicio"))),
                name="tarjeta_fechas_en_orden",
            ),
        ),
    ]
