"""
Pizarras con listas libres (§4.6, 2026-10-05): modelo `Lista`, permiso «Gestionar listas», y los
nombres de campos, restricciones y textos ya con «pizarra». Los datos (listas iniciales de cada
pizarra y tarjetas en ellas) los llena `tarjetas.0008`.
"""

import django.db.models.deletion
import django.db.models.functions.text
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("pizarras", "0002_proyecto_a_pizarra"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="pizarra",
            options={"ordering": ["nombre"], "verbose_name": "pizarra", "verbose_name_plural": "pizarras"},
        ),
        migrations.AlterField(
            model_name="pizarra",
            name="creado_por",
            field=models.ForeignKey(
                help_text="Quién la creó. El dueño actual está en sus miembros (puede haber cambiado).",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="pizarras_creadas",
                to=settings.AUTH_USER_MODEL,
                verbose_name="creada por",
            ),
        ),
        migrations.AlterField(
            model_name="pizarra",
            name="archivada_en",
            field=models.DateTimeField(
                blank=True,
                help_text="Vacío = activa. Archivada = solo lectura para todos sus miembros.",
                null=True,
                verbose_name="archivada en",
            ),
        ),
        migrations.AlterField(
            model_name="miembropizarra",
            name="pizarra",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="miembros",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AlterField(
            model_name="miembropizarra",
            name="puede_mover",
            field=models.BooleanField(default=True, verbose_name="puede mover tarjetas"),
        ),
        migrations.AddField(
            model_name="miembropizarra",
            name="puede_gestionar_listas",
            field=models.BooleanField(default=False, verbose_name="puede gestionar listas"),
        ),
        migrations.AlterField(
            model_name="invitacion",
            name="pizarra",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="invitaciones",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AlterField(
            model_name="tipotarjeta",
            name="pizarra",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="tipos",
                to="pizarras.pizarra",
                verbose_name="pizarra",
            ),
        ),
        migrations.AddConstraint(
            model_name="miembropizarra",
            constraint=models.UniqueConstraint(fields=("pizarra", "usuario"), name="miembro_unico"),
        ),
        migrations.AddConstraint(
            model_name="miembropizarra",
            constraint=models.UniqueConstraint(
                condition=models.Q(("rol", "dueno")),
                fields=("pizarra",),
                name="pizarra_un_solo_dueno",
            ),
        ),
        migrations.AddConstraint(
            model_name="invitacion",
            constraint=models.UniqueConstraint(
                models.F("pizarra"),
                django.db.models.functions.text.Lower("correo"),
                condition=models.Q(("estado", "pendiente")),
                name="invitacion_pendiente_unica",
            ),
        ),
        migrations.AddConstraint(
            model_name="tipotarjeta",
            constraint=models.UniqueConstraint(
                models.F("pizarra"),
                django.db.models.functions.text.Lower("nombre"),
                name="tipo_nombre_unico_en_pizarra",
            ),
        ),
        migrations.CreateModel(
            name="Lista",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("creado_en", models.DateTimeField(auto_now_add=True, verbose_name="creado en")),
                ("actualizado_en", models.DateTimeField(auto_now=True, verbose_name="actualizado en")),
                ("nombre", models.CharField(max_length=50, verbose_name="nombre")),
                ("posicion", models.PositiveIntegerField(default=0, verbose_name="posición")),
                (
                    "es_cierre",
                    models.BooleanField(
                        default=False,
                        help_text="Lo que llega aquí cuenta como terminado: no sale vencido ni en «Mis tarjetas».",
                        verbose_name="lista de cierre",
                    ),
                ),
                (
                    "pizarra",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="listas",
                        to="pizarras.pizarra",
                        verbose_name="pizarra",
                    ),
                ),
            ],
            options={
                "verbose_name": "lista",
                "verbose_name_plural": "listas",
                "ordering": ["posicion", "id"],
                "constraints": [
                    models.UniqueConstraint(
                        models.F("pizarra"),
                        django.db.models.functions.text.Lower("nombre"),
                        name="lista_nombre_unico_en_pizarra",
                    )
                ],
            },
        ),
    ]
