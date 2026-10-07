"""
`migrate` de Django con un paso previo: pasar a su etiqueta nueva una base que aún tiene apps con
la etiqueta anterior (§11 de la propuesta): `proyectos` → `pizarras` (2026-10-05) y `tarjetas` →
`actividades` (Etapa 3.8, 2026-10-06).

Django no sabe renombrar la etiqueta de una app: con la etiqueta nueva, el historial de
migraciones diría que la app nunca se aplicó e intentaría crear tablas que ya existen. Así que,
antes de migrar y en una sola transacción por app, se renombran sus tablas y se actualizan
`django_migrations` y `django_content_type`. Si no hay nada con la etiqueta vieja (base nueva o ya
pasada), no hace nada. Corre solo en cada `migrate`, también en el arranque del contenedor, para
que el despliegue no necesite pasos manuales.

`apps.core` va antes que Django en INSTALLED_APPS, por eso este comando reemplaza al original.
"""

from django.core.management.commands.migrate import Command as MigrateDeDjango
from django.db import connections, transaction

# (etiqueta vieja, etiqueta nueva, tablas). Con `tablas=None` se renombran todas las que empiezan
# con `<vieja>_`. En orden: una base muy vieja pasa por todas.
RENOMBRES = [
    (
        "proyectos",
        "pizarras",
        # Tal como las dejó su migración 0001 (antes de renombrar los modelos).
        {
            "proyectos_proyecto": "pizarras_proyecto",
            "proyectos_miembroproyecto": "pizarras_miembroproyecto",
            "proyectos_invitacion": "pizarras_invitacion",
            "proyectos_tipotarjeta": "pizarras_tipotarjeta",
        },
    ),
    # Tarjeta, sus M2M (asignados, tipos), Movimiento y ElementoChecklist.
    ("tarjetas", "actividades", None),
]


def renombrar_etiqueta(conexion, vieja, nueva, tablas=None, salida=None) -> bool:
    """Devuelve True si pasó algo de `vieja` a `nueva`."""
    existentes = set(conexion.introspection.table_names())
    if "django_migrations" not in existentes:
        return False
    with conexion.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations WHERE app = %s", [vieja])
        if not cursor.fetchone()[0]:
            return False
    if tablas is None:
        prefijo = f"{vieja}_"
        tablas = {t: nueva + "_" + t[len(prefijo) :] for t in existentes if t.startswith(prefijo)}
    q = conexion.ops.quote_name
    with transaction.atomic(using=conexion.alias), conexion.cursor() as cursor:
        for anterior, nombre in tablas.items():
            if anterior in existentes:
                cursor.execute(f"ALTER TABLE {q(anterior)} RENAME TO {q(nombre)}")
        cursor.execute("UPDATE django_migrations SET app = %s WHERE app = %s", [nueva, vieja])
        if "django_content_type" in existentes:
            cursor.execute(
                "UPDATE django_content_type SET app_label = %s WHERE app_label = %s",
                [nueva, vieja],
            )
    if salida:
        salida.write(f"La app «{vieja}» pasó a «{nueva}» (tablas e historial).")
    return True


class Command(MigrateDeDjango):
    def handle(self, *args, **options):
        conexion = connections[options["database"]]
        for vieja, nueva, tablas in RENOMBRES:
            renombrar_etiqueta(conexion, vieja, nueva, tablas, salida=self.stdout)
        return super().handle(*args, **options)
