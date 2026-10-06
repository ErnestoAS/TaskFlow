"""
«Lo que llega a [lista] cuenta como terminado» pasa del elemento de la checklist a la tarjeta que
tiene la checklist (2026-10-06, §4.6). Cada tarjeta se queda con la lista que más usaban sus
elementos convertidos (si empatan, la del primero). `0011` quita el campo del elemento: va
aparte porque PostgreSQL no deja alterar una tabla con restricciones diferidas pendientes en la
misma transacción en la que se actualizaron sus filas.
"""

from collections import Counter

import django.db.models.deletion
from django.db import migrations, models


def a_la_tarjeta(apps, schema_editor):
    Elemento = apps.get_model("tarjetas", "ElementoChecklist")
    Tarjeta = apps.get_model("tarjetas", "Tarjeta")
    por_tarjeta: dict[int, Counter] = {}
    elementos = Elemento.objects.filter(
        tarjeta_creada__isnull=False, lista_terminado__isnull=False
    ).order_by("tarjeta_id", "posicion", "id")
    for e in elementos:
        por_tarjeta.setdefault(e.tarjeta_id, Counter())[e.lista_terminado_id] += 1
    for tarjeta_id, conteo in por_tarjeta.items():
        # most_common respeta el orden de llegada al empatar: gana la del primer elemento.
        Tarjeta.objects.filter(pk=tarjeta_id).update(lista_terminado_id=conteo.most_common(1)[0][0])


def al_elemento(apps, schema_editor):
    Elemento = apps.get_model("tarjetas", "ElementoChecklist")
    for e in Elemento.objects.filter(
        tarjeta_creada__isnull=False, tarjeta__lista_terminado__isnull=False
    ).select_related("tarjeta"):
        e.lista_terminado_id = e.tarjeta.lista_terminado_id
        e.save(update_fields=["lista_terminado"])


class Migration(migrations.Migration):
    dependencies = [
        ("pizarras", "0003_listas_y_permisos"),
        ("tarjetas", "0009_sin_estatus"),
    ]

    operations = [
        migrations.AddField(
            model_name="tarjeta",
            name="lista_terminado",
            field=models.ForeignKey(
                blank=True,
                help_text="Vacía: los elementos de la checklist se palomean a mano.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="+",
                to="pizarras.lista",
                verbose_name="lo que llega a esta lista cuenta como terminado",
            ),
        ),
        migrations.RunPython(a_la_tarjeta, al_elemento),
    ]
