"""
«Proyecto» pasa a llamarse «Pizarra» en todo el sistema (Ernesto, 2026-10-05; §4.6 y §11).

Solo renombra (modelos, campos y la etiqueta de la app, que antes era `proyectos`): no cambia
datos. Las restricciones que mencionan el campo `proyecto` se quitan antes y se vuelven a crear
con `pizarra` en la migración siguiente, para que sus nombres también cuadren.

Las bases que ya existían tienen el historial y las tablas con la etiqueta vieja; el comando
`migrate` de `apps.core` los pasa a `pizarras` antes de migrar (ver ese comando).
"""

from django.db import migrations


class Migration(migrations.Migration):
    # Después de todas las migraciones de `tarjetas` que aún apuntan a `pizarras.proyecto`: en
    # una base nueva, renombrar antes las dejaría con una referencia a un modelo que ya no existe.
    dependencies = [("pizarras", "0001_initial"), ("tarjetas", "0006_prioridad")]

    operations = [
        migrations.RemoveConstraint(model_name="miembroproyecto", name="miembro_unico"),
        migrations.RemoveConstraint(model_name="miembroproyecto", name="proyecto_un_solo_dueno"),
        migrations.RemoveConstraint(model_name="invitacion", name="invitacion_pendiente_unica"),
        migrations.RemoveConstraint(
            model_name="tipotarjeta", name="tipo_nombre_unico_en_proyecto"
        ),
        migrations.RenameModel(old_name="Proyecto", new_name="Pizarra"),
        migrations.RenameModel(old_name="MiembroProyecto", new_name="MiembroPizarra"),
        migrations.RenameField(model_name="pizarra", old_name="archivado_en", new_name="archivada_en"),
        migrations.RenameField(model_name="miembropizarra", old_name="proyecto", new_name="pizarra"),
        migrations.RenameField(model_name="invitacion", old_name="proyecto", new_name="pizarra"),
        migrations.RenameField(model_name="tipotarjeta", old_name="proyecto", new_name="pizarra"),
        migrations.RenameField(
            model_name="miembropizarra", old_name="puede_cambiar_estatus", new_name="puede_mover"
        ),
    ]
