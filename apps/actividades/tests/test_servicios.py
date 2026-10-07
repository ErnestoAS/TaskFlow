import datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.actividades import servicios
from apps.actividades.models import Actividad, Movimiento
from apps.pizarras import servicios as pizarras
from apps.pizarras.servicios import PermisoDenegado

pytestmark = pytest.mark.django_db


def _orden(lista):
    return list(lista.actividades.order_by("posicion").values_list("titulo", flat=True))


def _historial(t):
    return list(
        t.movimientos.order_by("fecha", "id").values_list("lista_anterior", "lista_nueva", "nota")
    )


# --- crear y editar ----------------------------------------------------------------------------


def test_crear_actividad_con_el_puro_titulo(pizarra, dueno, listas):
    t = servicios.crear_actividad(pizarra, dueno, titulo=" Reservar auditorio ")
    assert (t.titulo, t.descripcion, t.lista, t.posicion) == (
        "Reservar auditorio",
        "",
        listas["Pendiente"],  # la primera lista
        0,
    )
    assert t.fecha_solicitud is None and t.fecha_fin is None
    assert list(t.asignados.all()) == [] and list(t.tipos.all()) == []
    assert _historial(t) == [("", "Pendiente", "")]
    assert t.movimientos.get().usuario == dueno


def test_la_actividad_nueva_va_al_final_de_su_lista(pizarra, dueno, listas):
    servicios.crear_actividad(pizarra, dueno, titulo="a", lista=listas["En curso"])
    b = servicios.crear_actividad(pizarra, dueno, titulo="b", lista=listas["En curso"])
    assert b.posicion == 1 and _orden(listas["En curso"]) == ["a", "b"]


def test_con_arriba_va_al_principio_de_su_lista(pizarra, dueno, listas):
    """El «+» del encabezado de la lista (Etapa 3.8)."""
    servicios.crear_actividad(pizarra, dueno, titulo="a", lista=listas["En curso"])
    servicios.crear_actividad(pizarra, dueno, titulo="b", lista=listas["En curso"])
    c = servicios.crear_actividad(pizarra, dueno, titulo="c", lista=listas["En curso"], arriba=True)
    assert c.posicion == 0 and _orden(listas["En curso"]) == ["c", "a", "b"]


def test_se_crea_con_su_checklist(pizarra, dueno, crear_usuario, agregar_miembro):
    """Mismo formulario de alta y edición (Etapa 3.8): la checklist va con el permiso «Crear»."""
    luis = crear_usuario()
    agregar_miembro(luis)
    pizarras.cambiar_permisos(pizarra, dueno, luis, editar=False)
    t = servicios.crear_actividad(pizarra, luis, titulo="a", checklist=[" Uno ", "Dos"])
    assert list(t.checklist.values_list("texto", "posicion", "hecho")) == [
        ("Uno", 0, False),
        ("Dos", 1, False),
    ]
    with pytest.raises(ValidationError):
        servicios.crear_actividad(pizarra, luis, titulo="b", checklist=["  "])


def test_el_titulo_es_obligatorio(pizarra, dueno):
    with pytest.raises(ValidationError) as e:
        servicios.crear_actividad(pizarra, dueno, titulo=" ")
    assert set(e.value.message_dict) == {"titulo"}


def test_la_lista_debe_ser_de_la_pizarra(pizarra, dueno):
    otra = pizarras.crear_pizarra(dueno, "Otra")
    ajena = pizarras.crear_lista(otra, dueno, "Pendiente")
    with pytest.raises(ValidationError):
        servicios.crear_actividad(pizarra, dueno, titulo="a", lista=ajena)


def test_fecha_de_solicitud_opcional_y_vence_no_anterior(pizarra, dueno):
    lunes = datetime.date(2026, 10, 5)
    t = servicios.crear_actividad(
        pizarra, dueno, titulo="a", fecha_solicitud=lunes, fecha_fin=datetime.date(2026, 10, 9)
    )
    assert t.fecha_solicitud == lunes
    with pytest.raises(ValidationError) as e:
        servicios.editar_actividad(t, dueno, fecha_fin=datetime.date(2026, 10, 1))
    assert set(e.value.message_dict) == {"fecha_fin"}
    with pytest.raises(ValidationError):
        servicios.crear_actividad(
            pizarra, dueno, titulo="b", fecha_solicitud=lunes, fecha_fin=datetime.date(2026, 10, 4)
        )
    # Sin fecha de solicitud, «Vence el» puede ser cualquiera.
    servicios.editar_actividad(t, dueno, fecha_solicitud=None, fecha_fin=datetime.date(2026, 1, 1))
    t.refresh_from_db()
    assert (t.fecha_solicitud, t.fecha_fin) == (None, datetime.date(2026, 1, 1))


def test_la_bd_tambien_exige_fechas_en_orden(pizarra, dueno, listas):
    with pytest.raises(IntegrityError), transaction.atomic():
        Actividad.objects.create(
            pizarra=pizarra,
            lista=listas["Pendiente"],
            titulo="a",
            fecha_solicitud=datetime.date(2026, 10, 5),
            fecha_fin=datetime.date(2026, 10, 1),
        )


def test_solo_se_asigna_a_miembros_y_tipos_de_la_pizarra(pizarra, dueno, crear_usuario):
    with pytest.raises(ValidationError):
        servicios.crear_actividad(pizarra, dueno, titulo="a", asignados=[crear_usuario()])
    otra = pizarras.crear_pizarra(dueno, "Otra")
    tipo_ajeno = pizarras.crear_tipo(otra, dueno, nombre="Ajeno", color="#000000")
    with pytest.raises(ValidationError):
        servicios.crear_actividad(pizarra, dueno, titulo="a", tipos=[tipo_ajeno])


def test_varios_tipos_y_asignados(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t1 = pizarras.crear_tipo(pizarra, dueno, nombre="Logística", color="#f08c00")
    t2 = pizarras.crear_tipo(pizarra, dueno, nombre="Urgente", color="#c92a2a")
    t = servicios.crear_actividad(
        pizarra, dueno, titulo="a", asignados=[dueno, luis], tipos=[t1, t2]
    )
    assert set(t.asignados.all()) == {dueno, luis} and set(t.tipos.all()) == {t1, t2}


def test_editar_la_lista_la_mueve_al_final_y_pide_mover(
    pizarra, dueno, listas, crear_usuario, agregar_miembro
):
    """Mismo formulario de alta y edición (Etapa 3.8): cambiar la lista es un movimiento."""
    servicios.crear_actividad(pizarra, dueno, titulo="ya", lista=listas["Finalizada"])
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.editar_actividad(t, dueno, titulo="a2", lista=listas["Finalizada"].pk)
    assert (t.titulo, t.lista, t.posicion) == ("a2", listas["Finalizada"], 1)
    assert _historial(t)[-1] == ("Pendiente", "Finalizada", "")
    luis = crear_usuario()
    agregar_miembro(luis)
    pizarras.cambiar_permisos(pizarra, dueno, luis, mover=False)
    servicios.editar_actividad(t, luis, titulo="a3", lista=listas["Finalizada"].pk)  # misma lista
    with pytest.raises(PermisoDenegado):
        servicios.editar_actividad(t, luis, lista=listas["Pendiente"])
    t.refresh_from_db()
    assert (t.titulo, t.lista) == ("a3", listas["Finalizada"])


def test_sin_prioridad(pizarra, dueno):
    """Se quitó en la Etapa 3.8: ya no es un campo editable."""
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.editar_actividad(t, dueno, descripcion="  Con detalle ")
    t.refresh_from_db()
    assert t.descripcion == "Con detalle"
    with pytest.raises(ValidationError):
        servicios.editar_actividad(t, dueno, prioridad="urgente")


# --- mover -------------------------------------------------------------------------------------


def test_mover_a_otra_lista_en_una_posicion(pizarra, dueno, listas):
    pend, curso = listas["Pendiente"], listas["En curso"]
    a = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.crear_actividad(pizarra, dueno, titulo="b")
    servicios.crear_actividad(pizarra, dueno, titulo="x", lista=curso)
    servicios.crear_actividad(pizarra, dueno, titulo="y", lista=curso)
    servicios.mover_actividad(a, dueno, curso, 1)
    assert _orden(pend) == ["b"] and _orden(curso) == ["x", "a", "y"]
    assert list(pend.actividades.values_list("posicion", flat=True)) == [0]  # sin huecos
    assert _historial(a)[-1] == ("Pendiente", "En curso", "")


def test_mover_sin_posicion_va_al_final_y_reordenar_no_deja_historial(pizarra, dueno, listas):
    a = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.crear_actividad(pizarra, dueno, titulo="b")
    servicios.crear_actividad(pizarra, dueno, titulo="c")
    servicios.mover_actividad(a, dueno, listas["Pendiente"])
    assert _orden(listas["Pendiente"]) == ["b", "c", "a"]
    servicios.mover_actividad(a, dueno, listas["Pendiente"], 0)
    assert _orden(listas["Pendiente"]) == ["a", "b", "c"]
    assert len(_historial(a)) == 1  # solo la creación


def test_mover_solo_a_listas_de_la_pizarra(pizarra, dueno):
    a = servicios.crear_actividad(pizarra, dueno, titulo="a")
    otra = pizarras.crear_pizarra(dueno, "Otra")
    with pytest.raises(ValidationError):
        servicios.mover_actividad(a, dueno, otra.listas.first())


def test_el_historial_guarda_el_nombre_de_entonces(pizarra, dueno, listas):
    a = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.mover_actividad(a, dueno, listas["En curso"])
    pizarras.editar_lista(listas["En curso"], dueno, nombre="Haciéndose")
    servicios.mover_actividad(a, dueno, listas["Finalizada"])
    assert _historial(a) == [
        ("", "Pendiente", ""),
        ("Pendiente", "En curso", ""),
        ("Haciéndose", "Finalizada", ""),
    ]


def test_cada_permiso_se_respeta(pizarra, dueno, crear_usuario, agregar_miembro, listas):
    luis = crear_usuario()
    agregar_miembro(luis, crear=False, editar=False, mover=False, eliminar=False)
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.crear_actividad(pizarra, luis, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.editar_actividad(t, luis, titulo="c")
    with pytest.raises(PermisoDenegado):
        servicios.mover_actividad(t, luis, listas["En curso"])
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_actividad(t, luis)
    pizarras.cambiar_permisos(
        pizarra, dueno, luis, crear=True, editar=True, mover=True, eliminar=True
    )
    servicios.crear_actividad(pizarra, luis, titulo="a")
    servicios.editar_actividad(t, luis, titulo="c")
    servicios.mover_actividad(t, luis, listas["En curso"])
    servicios.eliminar_actividad(t, luis)
    assert not Actividad.objects.filter(pk=t.pk).exists()


def test_un_no_miembro_no_toca_actividades(pizarra, dueno, crear_usuario, listas):
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    with pytest.raises(PermisoDenegado):
        servicios.mover_actividad(t, crear_usuario(), listas["Finalizada"])


def test_pizarra_archivada_no_admite_cambios(pizarra, dueno, listas):
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    pizarras.archivar(pizarra, dueno)
    with pytest.raises(PermisoDenegado):
        servicios.mover_actividad(t, dueno, listas["En curso"])
    with pytest.raises(PermisoDenegado):
        servicios.crear_actividad(pizarra, dueno, titulo="a")


def test_borrar_la_cuenta_conserva_el_historial(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.mover_actividad(t, luis, pizarra.listas.get(nombre="En curso"))
    luis.delete()
    assert Movimiento.objects.get(actividad=t, lista_nueva="En curso").usuario is None


def test_eliminar_actividad_renumera_su_lista(pizarra, dueno, listas):
    a = servicios.crear_actividad(pizarra, dueno, titulo="a")
    servicios.crear_actividad(pizarra, dueno, titulo="b")
    servicios.eliminar_actividad(a, dueno)
    assert list(listas["Pendiente"].actividades.values_list("posicion", flat=True)) == [0]


# --- checklist ---------------------------------------------------------------------------------


@pytest.fixture
def padre(pizarra, dueno):
    t = servicios.crear_actividad(pizarra, dueno, titulo="Programa del evento")
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


def test_convertir_crea_actividad_enlazada(padre, dueno):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno, descripcion="Con detalle")
    e.refresh_from_db()
    assert (nueva.titulo, nueva.lista, nueva.pizarra, nueva.descripcion) == (
        "Asignar salas",
        padre.lista,
        padre.pizarra,
        "Con detalle",
    )
    assert e.actividad_creada == nueva and nueva.elemento_origen == e
    # Sin lista de terminado en la actividad, se palomea a mano.
    assert padre.lista_terminado is None and not e.automatico
    assert ("", "", "convirtió «Asignar salas» de la checklist en actividad") in _historial(padre)
    assert ("", "", "la creó desde la checklist de «Programa del evento»") in _historial(nueva)
    with pytest.raises(ValidationError):
        servicios.convertir_elemento(e, dueno)  # ya convertido


def test_el_elemento_se_palomea_al_llegar_a_la_lista_de_su_actividad(padre, dueno, listas):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_actividad(padre, dueno, lista_terminado=listas["En curso"].pk)
    e.refresh_from_db()
    assert e.automatico and not e.esta_hecho
    servicios.mover_actividad(nueva, dueno, listas["En curso"])
    e.refresh_from_db()
    assert e.esta_hecho
    servicios.mover_actividad(nueva, dueno, listas["Finalizada"])  # pasa de largo: ya no está ahí
    e.refresh_from_db()
    assert not e.esta_hecho
    with pytest.raises(ValidationError):
        servicios.editar_elemento(e, dueno, hecho=True)  # automático: no se palomea a mano


def test_una_lista_para_toda_la_checklist(padre, dueno, listas):
    e1, e2, e3 = list(padre.checklist.all())
    a = servicios.convertir_elemento(e1, dueno)
    b = servicios.convertir_elemento(e2, dueno)
    servicios.editar_actividad(padre, dueno, lista_terminado=listas["Finalizada"].pk)
    servicios.mover_actividad(a, dueno, listas["Finalizada"])
    servicios.mover_actividad(b, dueno, listas["En curso"])
    hechos = {e.texto: e.esta_hecho for e in padre.checklist.all()}
    assert hechos == {"Confirmar ponentes": True, "Asignar salas": False, "Imprimir": False}
    assert not e3.automatico  # sin actividad, siempre a mano


def test_quitar_la_lista_de_terminado_conserva_el_estado(padre, dueno, listas):
    e = padre.checklist.get(texto="Imprimir")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_elemento(e, dueno, hecho=False)
    servicios.editar_actividad(padre, dueno, lista_terminado=listas["En curso"].pk)
    servicios.mover_actividad(nueva, dueno, listas["En curso"])
    servicios.editar_actividad(padre, dueno, lista_terminado=None)  # a manual
    e.refresh_from_db()
    assert not e.automatico and e.esta_hecho  # la actividad estaba en la lista: queda palomeado
    servicios.editar_elemento(e, dueno, hecho=False)
    e.refresh_from_db()
    assert not e.esta_hecho


def test_la_lista_de_terminado_es_de_la_pizarra_y_no_la_propia(padre, dueno):
    otra = pizarras.crear_pizarra(dueno, "Otra")
    ajena = pizarras.crear_lista(otra, dueno, "Hecho")
    for lista in (ajena, padre.lista):  # otra pizarra, o donde ya está la actividad
        with pytest.raises(ValidationError) as e:
            servicios.editar_actividad(padre, dueno, lista_terminado=lista.pk)
        assert set(e.value.message_dict) == {"lista_terminado"}
    with pytest.raises(ValidationError):
        servicios.editar_elemento(padre.checklist.first(), dueno, lista_terminado=padre.lista.pk)


def test_eliminar_la_actividad_creada_devuelve_el_elemento_a_texto(padre, dueno, listas):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.editar_actividad(padre, dueno, lista_terminado=listas["En curso"].pk)
    servicios.mover_actividad(nueva, dueno, listas["En curso"])
    servicios.eliminar_actividad(nueva, dueno)
    e.refresh_from_db()
    assert e.actividad_creada is None and not e.automatico
    assert e.hecho  # conserva que estaba hecho (la actividad estaba en la lista elegida)


def test_eliminar_la_original_deja_la_nueva_sin_origen(padre, dueno):
    e = padre.checklist.get(texto="Asignar salas")
    nueva = servicios.convertir_elemento(e, dueno)
    servicios.eliminar_actividad(padre, dueno)
    nueva = Actividad.objects.get(pk=nueva.pk)
    assert not hasattr(nueva, "elemento_origen")


def test_eliminar_la_lista_elegida_pasa_la_checklist_a_manual(padre, dueno):
    ideas = pizarras.crear_lista(padre.pizarra, dueno, "Ideas")
    e = padre.checklist.get(texto="Asignar salas")
    servicios.convertir_elemento(e, dueno)
    servicios.editar_actividad(padre, dueno, lista_terminado=ideas.pk)
    pizarras.eliminar_lista(ideas, dueno)
    padre.refresh_from_db()
    e.refresh_from_db()
    assert padre.lista_terminado is None and not e.automatico and not e.esta_hecho


# --- checklist: 400 caracteres y «Mover a … al completar» (Etapa 3.8) --------------------------


def test_elementos_de_hasta_400_caracteres(padre, dueno):
    e = servicios.agregar_elemento(padre, dueno, "x" * 400)
    assert len(e.texto) == 400
    with pytest.raises(ValidationError):
        servicios.agregar_elemento(padre, dueno, "x" * 401)


def test_al_completar_la_mueve_al_final_una_vez(
    padre, dueno, listas, crear_usuario, agregar_miembro
):
    servicios.crear_actividad(
        pizarra=padre.pizarra, usuario=dueno, titulo="ya", lista=listas["Finalizada"]
    )
    servicios.editar_actividad(padre, dueno, lista_al_completar=listas["Finalizada"].pk)
    a, b, c = padre.checklist.all()
    # Quien palomea el último no necesita «Mover»: la lista la eligió quien tenía «Editar».
    luis = crear_usuario()
    agregar_miembro(luis)
    pizarras.cambiar_permisos(padre.pizarra, dueno, luis, mover=False)
    servicios.editar_elemento(a, luis, hecho=True)
    servicios.editar_elemento(b, luis, hecho=True)
    padre.refresh_from_db()
    assert padre.lista == listas["Pendiente"]
    servicios.editar_elemento(c, luis, hecho=True)
    padre.refresh_from_db()
    assert (padre.lista, padre.posicion) == (listas["Finalizada"], 1)
    assert _historial(padre)[-1] == ("Pendiente", "Finalizada", "")
    # Despalomear no la regresa; volver a completarla estando ahí no hace nada.
    servicios.editar_elemento(c, luis, hecho=False)
    servicios.editar_elemento(c, luis, hecho=True)
    padre.refresh_from_db()
    assert padre.lista == listas["Finalizada"] and len(_historial(padre)) == 2


def test_elegir_la_lista_con_la_checklist_ya_completa_no_la_mueve(padre, dueno, listas):
    for e in padre.checklist.all():
        servicios.editar_elemento(e, dueno, hecho=True)
    servicios.editar_actividad(padre, dueno, lista_al_completar=listas["Finalizada"].pk)
    padre.refresh_from_db()
    assert (padre.lista, padre.lista_al_completar) == (listas["Pendiente"], listas["Finalizada"])


def test_quitar_el_ultimo_pendiente_tambien_la_completa(padre, dueno, listas):
    servicios.editar_actividad(padre, dueno, lista_al_completar=listas["En curso"].pk)
    a, b, c = padre.checklist.all()
    servicios.editar_elemento(a, dueno, hecho=True)
    servicios.editar_elemento(b, dueno, hecho=True)
    servicios.quitar_elemento(c, dueno)
    padre.refresh_from_db()
    assert padre.lista == listas["En curso"]


def test_al_completar_en_cascada_por_las_actividades_enlazadas(padre, dueno, listas):
    """La hija llega a la lista de terminado → se palomea en la madre → la madre se completa y se
    mueve (§4.7)."""
    a, b, c = padre.checklist.all()
    servicios.editar_elemento(a, dueno, hecho=True)
    servicios.editar_elemento(b, dueno, hecho=True)
    hija = servicios.convertir_elemento(c, dueno)
    servicios.editar_actividad(
        padre,
        dueno,
        lista_terminado=listas["Finalizada"].pk,
        lista_al_completar=listas["En curso"].pk,
    )
    padre.refresh_from_db()
    assert padre.lista == listas["Pendiente"]
    servicios.mover_actividad(hija, dueno, listas["Finalizada"])
    padre.refresh_from_db()
    assert padre.lista == listas["En curso"]


def test_lista_al_completar_de_la_pizarra(pizarra, dueno, listas):
    otra = pizarras.crear_pizarra(dueno, "Otra")
    ajena = pizarras.crear_lista(otra, dueno, "Pendiente")
    with pytest.raises(ValidationError) as e:
        servicios.crear_actividad(pizarra, dueno, titulo="a", lista_al_completar=ajena.pk)
    assert set(e.value.message_dict) == {"lista_al_completar"}
    t = servicios.crear_actividad(
        pizarra, dueno, titulo="a", lista_al_completar=listas["Finalizada"]
    )
    assert t.lista_al_completar == listas["Finalizada"]


def test_convertir_un_elemento_largo_cabe_en_el_historial(padre, dueno):
    """La nota del historial tiene 300 caracteres; el elemento, 400 (Etapa 3.8)."""
    e = servicios.agregar_elemento(padre, dueno, "x" * 400)
    servicios.convertir_elemento(e, dueno, titulo="x" * 200, descripcion=e.texto)
    nota = padre.movimientos.order_by("-fecha", "-id").first().nota
    assert len(nota) <= 300 and "…" in nota


def test_convertir_un_elemento_largo_parte_titulo_y_descripcion(padre, dueno):
    """Sin título, el servidor parte el texto como la PWA: lo que no cabe va a la descripción."""
    texto = ("palabra " * 50).strip()  # 399 caracteres
    e = servicios.agregar_elemento(padre, dueno, texto)
    nueva = servicios.convertir_elemento(e, dueno)
    assert len(nueva.titulo) <= 200 and not nueva.titulo.endswith(" ")
    assert f"{nueva.titulo} {nueva.descripcion}" == texto
    e.refresh_from_db()
    assert e.texto == nueva.titulo


def test_partir_titulo():
    assert servicios.partir_titulo("corto") == ("corto", "")
    assert servicios.partir_titulo("a" * 250) == ("a" * 200, "a" * 50)  # sin espacios: corte duro
    titulo, resto = servicios.partir_titulo("uno dos tres", tope=8)
    assert (titulo, resto) == ("uno dos", "tres")


def test_el_titulo_no_pasa_de_200(pizarra, dueno):
    with pytest.raises(ValidationError) as e:
        servicios.crear_actividad(pizarra, dueno, titulo="x" * 201)
    assert set(e.value.message_dict) == {"titulo"}


def test_el_elemento_sigue_el_titulo_de_su_actividad(padre, dueno):
    """Editar el título de la actividad enlazada cambia su elemento en la checklist de la madre; el
    texto de un elemento convertido no se edita por su lado (§4.7)."""
    e = padre.checklist.get(texto="Asignar salas")
    hija = servicios.convertir_elemento(e, dueno, titulo="Salas para el evento")
    e.refresh_from_db()
    assert e.texto == "Salas para el evento"
    servicios.editar_actividad(hija, dueno, titulo="Salas A y B")
    e.refresh_from_db()
    assert e.texto == "Salas A y B"
    with pytest.raises(ValidationError) as error:
        servicios.editar_elemento(e, dueno, texto="Otra cosa")
    assert set(error.value.message_dict) == {"texto"}
