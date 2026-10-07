"""`actividades.0010` (antes `tarjetas.0010`): la lista de terminado pasa de cada elemento a su
actividad (2026-10-06)."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

ANTES = [("actividades", "0009_sin_estatus"), ("pizarras", "0003_listas_y_permisos")]
DESPUES = [
    ("actividades", "0011_sin_lista_terminado_en_elemento"),
    ("pizarras", "0004_sin_listas_de_cierre"),
]


def _migrar(destino=None):
    """Sin destino, a las últimas migraciones (como queda la base para las demás pruebas)."""
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    destino = destino or executor.loader.graph.leaf_nodes()
    executor.migrate(destino)
    return executor.loader.project_state(destino).apps


@pytest.mark.django_db(transaction=True)
def test_la_tarjeta_se_queda_con_la_lista_mas_usada_por_sus_elementos(crear_usuario):
    usuario = crear_usuario()
    apps = _migrar(ANTES)
    Pizarra = apps.get_model("pizarras", "Pizarra")
    Lista = apps.get_model("pizarras", "Lista")
    Tarjeta = apps.get_model("actividades", "Tarjeta")
    Elemento = apps.get_model("actividades", "ElementoChecklist")
    p = Pizarra.objects.create(nombre="Feria", creado_por_id=usuario.pk)
    pendiente, curso, fin = (
        Lista.objects.create(pizarra=p, nombre=n, posicion=i)
        for i, n in enumerate(("Pendiente", "En curso", "Finalizada"))
    )

    def tarjeta(titulo):
        return Tarjeta.objects.create(pizarra=p, lista=pendiente, titulo=titulo)

    padre, sin_lista = tarjeta("Programa"), tarjeta("Sin lista")
    for i, lista in enumerate((curso, fin, fin)):
        Elemento.objects.create(
            tarjeta=padre,
            texto=f"e{i}",
            posicion=i,
            tarjeta_creada=tarjeta(f"h{i}"),
            lista_terminado=lista,
        )
    Elemento.objects.create(tarjeta=sin_lista, texto="manual", tarjeta_creada=tarjeta("h"))
    try:
        apps = _migrar(DESPUES)
        Tarjeta = apps.get_model("actividades", "Tarjeta")
        assert Tarjeta.objects.get(pk=padre.pk).lista_terminado_id == fin.pk
        assert Tarjeta.objects.get(pk=sin_lista.pk).lista_terminado_id is None
        # Y de vuelta: cada elemento convertido recibe la de su tarjeta.
        apps = _migrar(ANTES)
        Elemento = apps.get_model("actividades", "ElementoChecklist")
        assert set(
            Elemento.objects.filter(tarjeta_id=padre.pk).values_list(
                "lista_terminado_id", flat=True
            )
        ) == {fin.pk}
    finally:
        _migrar()


@pytest.mark.django_db(transaction=True)
def test_tarjeta_pasa_a_actividad_sin_prioridad_y_con_notas_nuevas(crear_usuario):
    """`actividades.0012`–`0015` y `pizarras.0005`–`0006` (Etapa 3.8, 2026-10-06), ida y vuelta."""
    usuario = crear_usuario()
    apps = _migrar(DESPUES)
    Pizarra = apps.get_model("pizarras", "Pizarra")
    Lista = apps.get_model("pizarras", "Lista")
    Tipo = apps.get_model("pizarras", "TipoTarjeta")
    Tarjeta = apps.get_model("actividades", "Tarjeta")
    Elemento = apps.get_model("actividades", "ElementoChecklist")
    Movimiento = apps.get_model("actividades", "Movimiento")
    p = Pizarra.objects.create(nombre="Feria", creado_por_id=usuario.pk)
    lista = Lista.objects.create(pizarra=p, nombre="Pendiente", posicion=0)
    tipo = Tipo.objects.create(pizarra=p, nombre="Difusión", color="#0ea5e9")
    padre = Tarjeta.objects.create(pizarra=p, lista=lista, titulo="Programa", prioridad="urgente")
    padre.tipos.add(tipo)
    padre.asignados.add(usuario.pk)
    hija = Tarjeta.objects.create(pizarra=p, lista=lista, titulo="Salas")
    Elemento.objects.create(tarjeta=padre, texto="Salas", tarjeta_creada=hija)
    nota = Movimiento.objects.create(
        tarjeta=padre, nota="convirtió «Salas» de la checklist en tarjeta"
    )
    try:
        apps = _migrar()
        Actividad = apps.get_model("actividades", "Actividad")
        a = Actividad.objects.get(pk=padre.pk)
        assert not hasattr(a, "prioridad")
        assert [t.nombre for t in a.tipos.all()] == ["Difusión"]
        assert list(a.asignados.values_list("pk", flat=True)) == [usuario.pk]
        assert a.checklist.get().actividad_creada_id == hija.pk
        nueva = apps.get_model("actividades", "Movimiento").objects.get(pk=nota.pk).nota
        assert nueva == "convirtió «Salas» de la checklist en actividad"
        # `0015`: la fecha de inicio se conserva como de solicitud, y ahora puede quedar vacía.
        assert a.fecha_solicitud == timezone.localdate()
        sin_fecha = Actividad.objects.create(pizarra_id=p.pk, lista_id=lista.pk, titulo="Sin fecha")
        assert sin_fecha.fecha_solicitud is None
        # Y de vuelta: la prioridad regresa como «media» y la nota como estaba.
        apps = _migrar(DESPUES)
        Tarjeta = apps.get_model("actividades", "Tarjeta")
        assert Tarjeta.objects.get(pk=padre.pk).prioridad == "media"
        assert Tarjeta.objects.get(pk=sin_fecha.pk).fecha_inicio == timezone.localdate()
        Movimiento = apps.get_model("actividades", "Movimiento")
        assert Movimiento.objects.get(pk=nota.pk).nota.endswith("en tarjeta")
    finally:
        _migrar()
