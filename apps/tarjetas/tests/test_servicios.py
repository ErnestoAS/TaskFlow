import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.pizarras import servicios as pizarras
from apps.pizarras.servicios import PermisoDenegado
from apps.tarjetas import servicios
from apps.tarjetas.models import Movimiento, Tarjeta

pytestmark = pytest.mark.django_db


def _orden(lista):
    return list(lista.tarjetas.order_by("posicion").values_list("titulo", flat=True))


def _historial(t):
    return list(
        t.movimientos.order_by("fecha", "id").values_list("lista_anterior", "lista_nueva", "nota")
    )


# --- crear y editar ----------------------------------------------------------------------------


def test_crear_tarjeta_con_el_puro_titulo(pizarra, dueno, listas):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo=" Reservar auditorio ")
    assert (t.titulo, t.descripcion, t.lista, t.posicion) == (
        "Reservar auditorio",
        "",
        listas["Pendiente"],  # la primera lista
        0,
    )
    assert t.fecha_inicio == timezone.localdate() and t.fecha_fin is None
    assert list(t.asignados.all()) == [] and list(t.tipos.all()) == []
    assert _historial(t) == [("", "Pendiente", "")]
    assert t.movimientos.get().usuario == dueno


def test_la_tarjeta_nueva_va_al_final_de_su_lista(pizarra, dueno, listas):
    servicios.crear_tarjeta(pizarra, dueno, titulo="a", lista=listas["En curso"])
    b = servicios.crear_tarjeta(pizarra, dueno, titulo="b", lista=listas["En curso"])
    assert b.posicion == 1 and _orden(listas["En curso"]) == ["a", "b"]


def test_el_titulo_es_obligatorio(pizarra, dueno):
    with pytest.raises(ValidationError) as e:
        servicios.crear_tarjeta(pizarra, dueno, titulo=" ")
    assert set(e.value.message_dict) == {"titulo"}


def test_la_lista_debe_ser_de_la_pizarra(pizarra, dueno):
    otra = pizarras.crear_pizarra(dueno, "Otra")
    ajena = pizarras.crear_lista(otra, dueno, "Pendiente")
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(pizarra, dueno, titulo="a", lista=ajena)


def test_fecha_de_inicio_editable_y_limite_no_anterior(pizarra, dueno):
    lunes = datetime.date(2026, 10, 5)
    t = servicios.crear_tarjeta(
        pizarra, dueno, titulo="a", fecha_inicio=lunes, fecha_fin=datetime.date(2026, 10, 9)
    )
    assert t.fecha_inicio == lunes
    with pytest.raises(ValidationError) as e:
        servicios.editar_tarjeta(t, dueno, fecha_fin=datetime.date(2026, 10, 1))
    assert set(e.value.message_dict) == {"fecha_fin"}
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(
            pizarra, dueno, titulo="b", fecha_inicio=lunes, fecha_fin=datetime.date(2026, 10, 4)
        )


def test_la_bd_tambien_exige_fechas_en_orden(pizarra, dueno, listas):
    with pytest.raises(IntegrityError), transaction.atomic():
        Tarjeta.objects.create(
            pizarra=pizarra,
            lista=listas["Pendiente"],
            titulo="a",
            fecha_inicio=datetime.date(2026, 10, 5),
            fecha_fin=datetime.date(2026, 10, 1),
        )


def test_solo_se_asigna_a_miembros_y_tipos_de_la_pizarra(pizarra, dueno, crear_usuario):
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(pizarra, dueno, titulo="a", asignados=[crear_usuario()])
    otra = pizarras.crear_pizarra(dueno, "Otra")
    tipo_ajeno = pizarras.crear_tipo(otra, dueno, nombre="Ajeno", color="#000000")
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(pizarra, dueno, titulo="a", tipos=[tipo_ajeno])


def test_varios_tipos_y_asignados(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t1 = pizarras.crear_tipo(pizarra, dueno, nombre="Logística", color="#f08c00")
    t2 = pizarras.crear_tipo(pizarra, dueno, nombre="Urgente", color="#c92a2a")
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a", asignados=[dueno, luis], tipos=[t1, t2])
    assert set(t.asignados.all()) == {dueno, luis} and set(t.tipos.all()) == {t1, t2}


def test_editar_no_mueve(pizarra, dueno, listas):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    with pytest.raises(ValidationError):
        servicios.editar_tarjeta(t, dueno, lista=listas["Finalizada"])


def test_prioridad_por_omision_y_editable(pizarra, dueno):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    assert t.prioridad == "media"
    servicios.editar_tarjeta(t, dueno, prioridad="urgente", descripcion="  Con detalle ")
    t.refresh_from_db()
    assert (t.prioridad, t.descripcion) == ("urgente", "Con detalle")
    with pytest.raises(ValidationError):
        servicios.editar_tarjeta(t, dueno, prioridad="altisima")


# --- mover -------------------------------------------------------------------------------------


def test_mover_a_otra_lista_en_una_posicion(pizarra, dueno, listas):
    pend, curso = listas["Pendiente"], listas["En curso"]
    a = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    servicios.crear_tarjeta(pizarra, dueno, titulo="b")
    servicios.crear_tarjeta(pizarra, dueno, titulo="x", lista=curso)
    servicios.crear_tarjeta(pizarra, dueno, titulo="y", lista=curso)
    servicios.mover_tarjeta(a, dueno, curso, 1)
    assert _orden(pend) == ["b"] and _orden(curso) == ["x", "a", "y"]
    assert list(pend.tarjetas.values_list("posicion", flat=True)) == [0]  # sin huecos
    assert _historial(a)[-1] == ("Pendiente", "En curso", "")


def test_mover_sin_posicion_va_al_final_y_reordenar_no_deja_historial(pizarra, dueno, listas):
    a = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    servicios.crear_tarjeta(pizarra, dueno, titulo="b")
    servicios.crear_tarjeta(pizarra, dueno, titulo="c")
    servicios.mover_tarjeta(a, dueno, listas["Pendiente"])
    assert _orden(listas["Pendiente"]) == ["b", "c", "a"]
    servicios.mover_tarjeta(a, dueno, listas["Pendiente"], 0)
    assert _orden(listas["Pendiente"]) == ["a", "b", "c"]
    assert len(_historial(a)) == 1  # solo la creación


def test_mover_solo_a_listas_de_la_pizarra(pizarra, dueno):
    a = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    otra = pizarras.crear_pizarra(dueno, "Otra")
    with pytest.raises(ValidationError):
        servicios.mover_tarjeta(a, dueno, otra.listas.first())


def test_el_historial_guarda_el_nombre_de_entonces(pizarra, dueno, listas):
    a = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    servicios.mover_tarjeta(a, dueno, listas["En curso"])
    pizarras.editar_lista(listas["En curso"], dueno, nombre="Haciéndose")
    servicios.mover_tarjeta(a, dueno, listas["Finalizada"])
    assert _historial(a) == [
        ("", "Pendiente", ""),
        ("Pendiente", "En curso", ""),
        ("Haciéndose", "Finalizada", ""),
    ]


def test_cada_permiso_se_respeta(pizarra, dueno, crear_usuario, agregar_miembro, listas):
    luis = crear_usuario()
    agregar_miembro(luis, crear=False, editar=False, mover=False, eliminar=False)
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.crear_tarjeta(pizarra, luis, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.editar_tarjeta(t, luis, titulo="c")
    with pytest.raises(PermisoDenegado):
        servicios.mover_tarjeta(t, luis, listas["En curso"])
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_tarjeta(t, luis)
    pizarras.cambiar_permisos(
        pizarra, dueno, luis, crear=True, editar=True, mover=True, eliminar=True
    )
    servicios.crear_tarjeta(pizarra, luis, titulo="a")
    servicios.editar_tarjeta(t, luis, titulo="c")
    servicios.mover_tarjeta(t, luis, listas["En curso"])
    servicios.eliminar_tarjeta(t, luis)
    assert not Tarjeta.objects.filter(pk=t.pk).exists()


def test_un_no_miembro_no_toca_tarjetas(pizarra, dueno, crear_usuario, listas):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.mover_tarjeta(t, crear_usuario(), listas["Finalizada"])


def test_pizarra_archivada_no_admite_cambios(pizarra, dueno, listas):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    pizarras.archivar(pizarra, dueno)
    with pytest.raises(PermisoDenegado):
        servicios.mover_tarjeta(t, dueno, listas["En curso"])
    with pytest.raises(PermisoDenegado):
        servicios.crear_tarjeta(pizarra, dueno, titulo="a")


def test_borrar_la_cuenta_conserva_el_historial(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    servicios.mover_tarjeta(t, luis, pizarra.listas.get(nombre="En curso"))
    luis.delete()
    assert Movimiento.objects.get(tarjeta=t, lista_nueva="En curso").usuario is None


def test_eliminar_tarjeta_renumera_su_lista(pizarra, dueno, listas):
    a = servicios.crear_tarjeta(pizarra, dueno, titulo="a")
    servicios.crear_tarjeta(pizarra, dueno, titulo="b")
    servicios.eliminar_tarjeta(a, dueno)
    assert list(listas["Pendiente"].tarjetas.values_list("posicion", flat=True)) == [0]


# --- checklist ---------------------------------------------------------------------------------


@pytest.fixture
def padre(pizarra, dueno):
    t = servicios.crear_tarjeta(pizarra, dueno, titulo="Programa del evento")
    for texto in ("Confirmar ponentes", "Asignar salas", "Imprimir"):
        servicios.agregar_elemento(t, dueno, texto)
    return t


def test_agregar_palomear_ordenar_y_quitar(padre, dueno):
    a, b, c = padre.checklist.all()
    assert [e.posicion for e in (a, b, c)] == [0, 1, 2]
    servicios.editar_elemento(a, dueno, hecho=True, texto=" Confirmar a los ponentes ")
    a.refresh_from_db()
    assert a.esta_hecho and a.texto == "Confirmar a los ponentes"
    servicios.ordenar_checklist(padre, dueno, [c.pk, a.pk, b.pk])
    assert list(padre.checklist.values_list("texto", flat=True)) == [
        "Imprimir",
        "Confirmar a los ponentes",
        "Asignar salas",
    ]
    servicios.quitar_elemento(b, dueno)
    assert padre.checklist.count() == 2
    with pytest.raises(ValidationError):
        servicios.agregar_elemento(padre, dueno, "  ")


def test_la_checklist_requiere_editar_y_convertir_requiere_crear(
    padre, dueno, crear_usuario, agregar_miembro, pizarra
):
    luis = crear_usuario()
    agregar_miembro(luis, editar=False, crear=False)
    e = padre.checklist.first()
    with pytest.raises(PermisoDenegado):
        servicios.agregar_elemento(padre, luis, "Otro")
    with pytest.raises(PermisoDenegado):
        servicios.editar_elemento(e, luis, hecho=True)
    with pytest.raises(PermisoDenegado):
        servicios.convertir_elemento(e, luis)
    pizarras.cambiar_permisos(pizarra, dueno, luis, crear=True)
    servicios.convertir_elemento(e, luis)


def test_convertir_crea_tarjeta_enlazada(padre, dueno):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno, prioridad="alta")
    e.refresh_from_db()
    assert (nueva.titulo, nueva.lista, nueva.pizarra, nueva.prioridad) == (
        "Asignar salas",
        padre.lista,
        padre.pizarra,
        "alta",
    )
    assert e.tarjeta_creada == nueva and nueva.elemento_origen == e
    # Sin lista de terminado en la tarjeta, se palomea a mano.
    assert padre.lista_terminado is None and not e.automatico
    assert ("", "", "convirtió «Asignar salas» de la checklist en tarjeta") in _historial(padre)
    assert ("", "", "la creó desde la checklist de «Programa del evento»") in _historial(nueva)
    with pytest.raises(ValidationError):
        servicios.convertir_elemento(e, dueno)  # ya convertido


def test_el_elemento_se_palomea_al_llegar_a_la_lista_de_su_tarjeta(padre, dueno, listas):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_tarjeta(padre, dueno, lista_terminado=listas["En curso"].pk)
    e.refresh_from_db()
    assert e.automatico and not e.esta_hecho
    servicios.mover_tarjeta(nueva, dueno, listas["En curso"])
    e.refresh_from_db()
    assert e.esta_hecho
    servicios.mover_tarjeta(nueva, dueno, listas["Finalizada"])  # pasa de largo: ya no está ahí
    e.refresh_from_db()
    assert not e.esta_hecho
    with pytest.raises(ValidationError):
        servicios.editar_elemento(e, dueno, hecho=True)  # automático: no se palomea a mano


def test_una_lista_para_toda_la_checklist(padre, dueno, listas):
    e1, e2, e3 = list(padre.checklist.all())
    a = servicios.convertir_elemento(e1, dueno)
    b = servicios.convertir_elemento(e2, dueno)
    servicios.editar_tarjeta(padre, dueno, lista_terminado=listas["Finalizada"].pk)
    servicios.mover_tarjeta(a, dueno, listas["Finalizada"])
    servicios.mover_tarjeta(b, dueno, listas["En curso"])
    hechos = {e.texto: e.esta_hecho for e in padre.checklist.all()}
    assert hechos == {"Confirmar ponentes": True, "Asignar salas": False, "Imprimir": False}
    assert not e3.automatico  # sin tarjeta, siempre a mano


def test_quitar_la_lista_de_terminado_conserva_el_estado(padre, dueno, listas):
    e = padre.checklist.get(texto="Imprimir")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_elemento(e, dueno, hecho=False)
    servicios.editar_tarjeta(padre, dueno, lista_terminado=listas["En curso"].pk)
    servicios.mover_tarjeta(nueva, dueno, listas["En curso"])
    servicios.editar_tarjeta(padre, dueno, lista_terminado=None)  # a manual
    e.refresh_from_db()
    assert not e.automatico and e.esta_hecho  # la tarjeta estaba en la lista: queda palomeado
    servicios.editar_elemento(e, dueno, hecho=False)
    e.refresh_from_db()
    assert not e.esta_hecho


def test_la_lista_de_terminado_es_de_la_pizarra_y_no_la_propia(padre, dueno):
    otra = pizarras.crear_pizarra(dueno, "Otra")
    ajena = pizarras.crear_lista(otra, dueno, "Hecho")
    for lista in (ajena, padre.lista):  # otra pizarra, o donde ya está la tarjeta
        with pytest.raises(ValidationError) as e:
            servicios.editar_tarjeta(padre, dueno, lista_terminado=lista.pk)
        assert set(e.value.message_dict) == {"lista_terminado"}
    with pytest.raises(ValidationError):
        servicios.editar_elemento(padre.checklist.first(), dueno, lista_terminado=padre.lista.pk)


def test_eliminar_la_tarjeta_creada_devuelve_el_elemento_a_texto(padre, dueno, listas):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_tarjeta(padre, dueno, lista_terminado=listas["En curso"].pk)
    servicios.mover_tarjeta(nueva, dueno, listas["En curso"])
    servicios.eliminar_tarjeta(nueva, dueno)
    e.refresh_from_db()
    assert e.tarjeta_creada is None and not e.automatico
    assert e.hecho  # conserva que estaba hecho (la tarjeta estaba en la lista elegida)


def test_eliminar_la_original_deja_la_nueva_sin_origen(padre, dueno):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.eliminar_tarjeta(padre, dueno)
    nueva = Tarjeta.objects.get(pk=nueva.pk)
    assert not hasattr(nueva, "elemento_origen")


def test_eliminar_la_lista_elegida_pasa_la_checklist_a_manual(padre, dueno):
    ideas = pizarras.crear_lista(padre.pizarra, dueno, "Ideas")
    e = padre.checklist.get(texto="Asignar salas")
    servicios.convertir_elemento(e, dueno)
    servicios.editar_tarjeta(padre, dueno, lista_terminado=ideas.pk)
    pizarras.eliminar_lista(ideas, dueno)
    padre.refresh_from_db()
    e.refresh_from_db()
    assert padre.lista_terminado is None and not e.automatico and not e.esta_hecho
