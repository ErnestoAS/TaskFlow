"""Fuera `ElementoChecklist.lista_terminado`: ya se copió a la tarjeta en `0010`."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("actividades", "0010_lista_terminado_en_tarjeta")]

    operations = [
        migrations.RemoveField(model_name="elementochecklist", name="lista_terminado"),
    ]
