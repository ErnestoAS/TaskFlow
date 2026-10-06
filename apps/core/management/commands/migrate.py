"""
`migrate` de Django con un paso previo: pasar a `pizarras` una base que aún tiene la app con su
etiqueta anterior, `proyectos` (renombrada el 2026-10-05, §11 de la propuesta).

Django no sabe renombrar la etiqueta de una app: con la etiqueta nueva, el historial de
migraciones diría que `pizarras` nunca se aplicó e intentaría crear tablas que ya existen. Así que,
antes de migrar y en una sola transacción, se renombran las tablas de la app y se actualizan
`django_migrations` y `django_content_type`. Si no hay nada con la etiqueta vieja (base nueva o ya
pasada), no hace nada. Corre solo en cada `migrate`, también en el arranque del contenedor, para
que el despliegue no necesite pasos manuales.

`apps.core` va antes que Django en INSTALLED_APPS, por eso este comando reemplaza al original.
"""

from django.core.management.commands.migrate import Command as MigrateDeDjango
from django.db import connections, transaction

ETIQUETA_VIEJA = "proyectos"
ETIQUETA_NUEVA = "pizarras"

# Tablas de la app tal como las dejó su migración 0001 (antes de renombrar los modelos).
TABLAS = {
    "proyectos_proyecto": "pizarras_proyecto",
    "proyectos_miembroproyecto": "pizarras_miembroproyecto",
    "proyectos_invitacion": "pizarras_invitacion",
    "proyectos_tipotarjeta": "pizarras_tipotarjeta",
}


def renombrar_etiqueta(conexion, tablas=None, salida=None) -> bool:
    """Devuelve True si pasó algo de `proyectos` a `pizarras`."""
    tablas = TABLAS if tablas is None else tablas
    existentes = set(conexion.introspection.table_names())
    if "django_migrations" not in existentes:
        return False
    with conexion.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = %s", [ETIQUETA_VIEJA])
        if not cursor.fetchone()[0]:
            return False
    q = conexion.ops.quote_name
    with transaction.atomic(using=conexion.alias), conexion.cursor() as cursor:
        for vieja, nueva in tablas.items():
            if vieja in existentes:
                cursor.execute(f"ALTER TABLE {q(vieja)} RENAME TO {q(nueva)}")
        cursor.execute(
            "UPDATE django_migrations SET app = %s WHERE app = %s", [ETIQUETA_NUEVA, ETIQUETA_VIEJA]
        )
        if "django_content_type" in existentes:
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s",
                [ETIQUETA_NUEVA, ETIQUETA_VIEJA],
            )
    if salida:
        salida.write(f"La app «{ETIQUETA_VIEJA}» pasó a «{ETIQUETA_NUEVA}» (tablas e historial).")
    return True


class Command(MigrateDeDjango):
    def handle(self, *args, **options):
        renombrar_etiqueta(connections[options["database"]], salida=self.stdout)
        return super().handle(*args, **options)
