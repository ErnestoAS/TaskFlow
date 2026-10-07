"""
Esquema de la v3 (§4.6, 2026-10-05), primera parte: la tarjeta pasa de «proyecto» a «pizarra», gana
`lista`, `posicion` y `fecha_inicio` (aún opcionales: los llena `0008`), la descripción se vuelve
opcional, y nacen `Movimiento` (historial por listas) y `ElementoChecklist`. `0009` termina:
hace obligatorios los campos nuevos y quita `estatus` y `CambioEstatus`.

Va en tres migraciones porque PostgreSQL no deja alterar una tabla en la misma transacción en la
que se actualizaron sus filas con restricciones diferidas pendientes.
"""

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("actividades", "0006_prioridad"),
        ("pizarras", "0003_listas_y_permisos"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveIndex(model_name="tarjeta", name="tarjeta_proyecto_estatus"),
        migrations.RenameField(model_name="tarjeta", old_name="proyecto", new_name="pizarra"),
        migrations.AddField(
            model_name="tarjeta",
            name="lista",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.RESTRICT,
                related_name="tarjetas",
                to="pizarras.lista",
                verbose_name="lista",
            ),
        ),
        migrations.AddField(
            model_name="tarjeta",
            name="posicion",
            field=models.PositiveIntegerField(default=0, verbose_name="posición"),
        ),
        migrations.AddField(
            model_name="tarjeta",
            name="fecha_inicio",
            field=models.DateField(null=True, verbose_name="fecha de inicio"),
        ),
        migrations.AlterField(
            model_name="tarjeta",
            name="descripcion",
            field=models.TextField(blank=True, verbose_name="descripción"),
        ),
        migrations.AlterField(
            model_name="tarjeta",
            name="fecha_fin",
            field=models.DateField(blank=True, null=True, verbose_name="fecha límite"),
        ),
        migrations.AlterModelOptions(
            name="tarjeta",
            options={"ordering": ["posicion", "id"], "verbose_name": "tarjeta", "verbose_name_plural": "tarjetas"},
        ),
        migrations.CreateModel(
            name="Movimiento",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("lista_anterior", models.CharField(blank=True, max_length=50, verbose_name="lista anterior")),
                ("lista_nueva", models.CharField(blank=True, max_length=50, verbose_name="lista nueva")),
                ("nota", models.CharField(blank=True, max_length=300, verbose_name="nota")),
                ("fecha", models.DateTimeField(default=django.utils.timezone.now, verbose_name="fecha")),
                (
                    "tarjeta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="movimientos",
                        to="actividades.tarjeta",
                        verbose_name="tarjeta",
                    ),
                ),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        help_text="Vacío si la cuenta se borró: el movimiento se conserva («Usuario eliminado»).",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="movimientos",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="usuario",
                    ),
                ),
            ],
            options={
                "verbose_name": "movimiento",
                "verbose_name_plural": "historial",
                "ordering": ["-fecha", "-id"],
                "indexes": [models.Index(fields=["tarjeta", "-fecha"], name="movimiento_tarjeta_fecha")],
            },
        ),
        migrations.CreateModel(
            name="ElementoChecklist",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True, verbose_name="creado en")),
                ("actualizado_en", models.DateTimeField(auto_now=True, verbose_name="actualizado en")),
                ("texto", models.CharField(max_length=200, verbose_name="texto")),
                ("hecho", models.BooleanField(default=False, verbose_name="hecho")),
                ("posicion", models.PositiveIntegerField(default=0, verbose_name="posición")),
                (
                    "lista_terminado",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to="pizarras.lista",
                        verbose_name="se marca al pasar a",
                    ),
                ),
                (
                    "tarjeta",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="checklist",
                        to="actividades.tarjeta",
                        verbose_name="tarjeta",
                    ),
                ),
                (
                    "tarjeta_creada",
                    models.OneToOneField(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="elemento_origen",
                        to="actividades.tarjeta",
                        verbose_name="tarjeta creada",
                    ),
                ),
            ],
            options={
                "verbose_name": "elemento de checklist",
                "verbose_name_plural": "checklist",
                "ordering": ["posicion", "id"],
            },
        ),
    ]
