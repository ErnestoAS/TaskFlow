"""
Etapa 3.8 (2026-10-06, §4.7 de la propuesta): `TipoTarjeta` pasa a `TipoActividad`. A mano porque
`makemigrations` no detecta renombres sin preguntar; los nombres para mostrar van en la siguiente.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("pizarras", "0004_sin_listas_de_cierre")]

    operations = [migrations.RenameModel("TipoTarjeta", "TipoActividad")]
