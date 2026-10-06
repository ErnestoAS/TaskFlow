"""
Datos (§4.5, nota del 2026-10-01): antes de hacer obligatorio `Tarjeta.proyecto`, las tarjetas que
ya existían (la de prueba en producción) pasan a un proyecto «Tarjetas anteriores» en lugar de
borrarse. Su dueño es quien creó la primera tarjeta o, si no hay, el primer superusuario; los
asignados se vuelven miembros, porque solo los miembros pueden estar asignados.

También siembra el historial de estatus: una entrada de «creación» con el estatus actual y la
fecha de creación de cada tarjeta que aún no tenga historial.
"""

from django.db import migrations


def a_proyecto(apps, schema_editor):
    Tarjeta = apps.get_model("tarjetas", "Tarjeta")
    CambioEstatus = apps.get_model("tarjetas", "CambioEstatus")
    Proyecto = apps.get_model("pizarras", "Proyecto")
    MiembroProyecto = apps.get_model("pizarras", "MiembroProyecto")
    Usuario = apps.get_model("usuarios", "Usuario")

    huerfanas = Tarjeta.objects.filter(proyecto__isnull=True).order_by("creado_en", "pk")
    if huerfanas.exists():
        primera = huerfanas.filter(creada_por__isnull=False).first()
        dueno = primera.creada_por if primera else Usuario.objects.filter(is_superuser=True).order_by("pk").first()
        if dueno is None:
            raise RuntimeError(
                "Hay tarjetas sin proyecto y ningún usuario para ser su dueño. "
                "Crea un superusuario (createsuperuser) y vuelve a migrar."
            )
        proyecto = Proyecto.objects.create(nombre="Tarjetas anteriores", creado_por=dueno)
        MiembroProyecto.objects.create(proyecto=proyecto, usuario=dueno, rol="dueno")
        asignados = Usuario.objects.filter(tarjetas_asignadas__in=huerfanas).exclude(pk=dueno.pk).distinct()
        for usuario in asignados:
            MiembroProyecto.objects.get_or_create(proyecto=proyecto, usuario=usuario)
        huerfanas.update(proyecto=proyecto)

    for tarjeta in Tarjeta.objects.filter(cambios_estatus__isnull=True):
        CambioEstatus.objects.create(
            tarjeta=tarjeta,
            usuario=tarjeta.creada_por,
            estatus_anterior="",
            estatus_nuevo=tarjeta.estatus,
            fecha=tarjeta.creado_en,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("tarjetas", "0003_proyecto_tipos_historial"),
        ("pizarras", "0001_initial"),
        ("usuarios", "0001_initial"),
    ]

    operations = [migrations.RunPython(a_proyecto, migrations.RunPython.noop)]
