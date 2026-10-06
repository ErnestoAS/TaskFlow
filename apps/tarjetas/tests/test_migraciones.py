"""`tarjetas.0010`: la lista de terminado pasa de cada elemento a su tarjeta (2026-10-06)."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

ANTES = [("tarjetas", "0009_sin_estatus"), ("pizarras", "0003_listas_y_permisos")]
DESPUES = [
    ("tarjetas", "0011_sin_lista_terminado_en_elemento"),
    ("pizarras", "0004_sin_listas_de_cierre"),
]


def _migrar(destino):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(destino)
    return executor.loader.project_state(destino).apps


@pytest.mark.django_db(transaction=True)
def test_la_tarjeta_se_queda_con_la_lista_mas_usada_por_sus_elementos(crear_usuario):
    usuario = crear_usuario()
    apps = _migrar(ANTES)
    Pizarra = apps.get_model("pizarras", "Pizarra")
    Lista = apps.get_model("pizarras", "Lista")
    Tarjeta = apps.get_model("tarjetas", "Tarjeta")
    Elemento = apps.get_model("tarjetas", "ElementoChecklist")
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
        Tarjeta = apps.get_model("tarjetas", "Tarjeta")
        assert Tarjeta.objects.get(pk=padre.pk).lista_terminado_id == fin.pk
        assert Tarjeta.objects.get(pk=sin_lista.pk).lista_terminado_id is None
        # Y de vuelta: cada elemento convertido recibe la de su tarjeta.
        apps = _migrar(ANTES)
        Elemento = apps.get_model("tarjetas", "ElementoChecklist")
        assert set(
            Elemento.objects.filter(tarjeta_id=padre.pk).values_list(
                "lista_terminado_id", flat=True
            )
        ) == {fin.pk}
    finally:
        _migrar(DESPUES)
