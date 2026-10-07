"""
Datos de la v3 (§4.6, 2026-10-05): los estatus pasan a listas sin perder nada.

- Cada pizarra recibe las listas «Pendiente», «En curso» y «Finalizada» (esta, de cierre: sus
  tarjetas siguen sin salir vencidas) y cada tarjeta va a la de su estatus.
- Dentro de cada lista, el orden manual empieza igual que el tablero de antes: prioridad
  (urgente → baja), fecha de fin (sin fecha al final) y las más nuevas primero.
- `fecha_inicio` = el día de creación en la zona de TaskFlow. Si la tarjeta ya tenía una fecha de
  fin anterior (antes se permitía), se usa esa, para respetar «fin ≥ inicio».
- El historial de `CambioEstatus` se copia a `Movimiento` con los nombres de las listas.

Reversible: de vuelta, una tarjeta en lista de cierre queda «finalizada», en una lista llamada
«En curso», «en_curso», y en cualquier otra, «pendiente». Las listas, el orden manual, la fecha de
inicio y la checklist se pierden (no existían). En producción, la vuelta atrás recomendada sigue
siendo restaurar el respaldo que `taskflow desplegar` toma antes de migrar (docs/operacion.md).
"""

import datetime
import zoneinfo

from django.conf import settings
from django.db import migrations

NOMBRES = {"pendiente": "Pendiente", "en_curso": "En curso", "finalizada": "Finalizada"}
ORDEN_PRIORIDAD = {"urgente": 0, "alta": 1, "media": 2, "baja": 3}


def estatus_a_listas(apps, schema_editor):
    Pizarra = apps.get_model("pizarras", "Pizarra")
    Lista = apps.get_model("pizarras", "Lista")
    Tarjeta = apps.get_model("actividades", "Tarjeta")
    CambioEstatus = apps.get_model("actividades", "CambioEstatus")
    Movimiento = apps.get_model("actividades", "Movimiento")
    zona = zoneinfo.ZoneInfo(settings.TIME_ZONE)

    for pizarra in Pizarra.objects.all():
        listas = {
            clave: Lista.objects.create(
                pizarra=pizarra, nombre=nombre, posicion=i, es_cierre=clave == "finalizada"
            )
            for i, (clave, nombre) in enumerate(NOMBRES.items())
        }
        tarjetas = sorted(
            Tarjeta.objects.filter(pizarra=pizarra),
            key=lambda t: (
                ORDEN_PRIORIDAD.get(t.prioridad, 2),
                t.fecha_fin or datetime.date.max,
                -t.pk,
            ),
        )
        siguiente = dict.fromkeys(NOMBRES, 0)
        for t in tarjetas:
            clave = t.estatus if t.estatus in NOMBRES else "pendiente"
            t.lista = listas[clave]
            t.posicion = siguiente[clave]
            siguiente[clave] += 1
            inicio = t.creado_en.astimezone(zona).date()
            t.fecha_inicio = min(inicio, t.fecha_fin) if t.fecha_fin else inicio
        Tarjeta.objects.bulk_update(tarjetas, ["lista", "posicion", "fecha_inicio"])

    Movimiento.objects.bulk_create(
        Movimiento(
            tarjeta_id=c.tarjeta_id,
            usuario_id=c.usuario_id,
            lista_anterior=NOMBRES.get(c.estatus_anterior, ""),
            lista_nueva=NOMBRES.get(c.estatus_nuevo, c.estatus_nuevo),
            fecha=c.fecha,
        )
        for c in CambioEstatus.objects.all()
    )


def _estatus_de(nombre: str, es_cierre: bool) -> str:
    if es_cierre:
        return "finalizada"
    return "en_curso" if nombre.strip().lower() == "en curso" else "pendiente"


def listas_a_estatus(apps, schema_editor):
    Tarjeta = apps.get_model("actividades", "Tarjeta")
    CambioEstatus = apps.get_model("actividades", "CambioEstatus")
    Movimiento = apps.get_model("actividades", "Movimiento")
    Lista = apps.get_model("pizarras", "Lista")

    tarjetas = list(Tarjeta.objects.select_related("lista"))
    for t in tarjetas:
        t.estatus = _estatus_de(t.lista.nombre, t.lista.es_cierre) if t.lista else "pendiente"
    Tarjeta.objects.bulk_update(tarjetas, ["estatus"])

    # El historial guarda nombres: se traducen con las listas de cierre que existen hoy.
    cierre = {n.lower() for n in Lista.objects.filter(es_cierre=True).values_list("nombre", flat=True)}
    CambioEstatus.objects.all().delete()
    CambioEstatus.objects.bulk_create(
        CambioEstatus(
            tarjeta_id=m.tarjeta_id,
            usuario_id=m.usuario_id,
            estatus_anterior=(
                _estatus_de(m.lista_anterior, m.lista_anterior.lower() in cierre)
                if m.lista_anterior
                else ""
            ),
            estatus_nuevo=_estatus_de(m.lista_nueva, m.lista_nueva.lower() in cierre),
            fecha=m.fecha,
        )
        for m in Movimiento.objects.filter(nota="")
    )


class Migration(migrations.Migration):
    dependencies = [("actividades", "0007_pizarra_listas_checklist")]

    operations = [migrations.RunPython(estatus_a_listas, listas_a_estatus)]
