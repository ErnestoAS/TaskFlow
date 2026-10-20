"""Comentarios de las actividades (2026-10-20, §4.4): quién comenta, edita y borra."""

import pytest
from django.core.exceptions import ValidationError

from apps.actividades import servicios
from apps.actividades.models import Comentario, Movimiento
from apps.pizarras import servicios as pizarras
from apps.pizarras.servicios import PermisoDenegado


@pytest.fixture
def actividad(pizarra, dueno):
    return servicios.crear_actividad(pizarra, dueno, titulo="Con conversación")


def test_cualquier_miembro_comenta_aunque_no_pueda_editar(
    actividad, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis, crear=False, editar=False, mover=False, eliminar=False)
    c = servicios.comentar(actividad, luis, "  Ya hablé con proveedores.\nLlegan el jueves.  ")
    assert (c.autor, c.texto, c.editado_en) == (
        luis,
        "Ya hablé con proveedores.\nLlegan el jueves.",
        None,
    )
    # Comentar no es un movimiento: el historial solo tiene la creación.
    assert Movimiento.objects.filter(actividad=actividad).count() == 1


def test_el_texto_es_obligatorio_y_tiene_tope(actividad, dueno):
    with pytest.raises(ValidationError):
        servicios.comentar(actividad, dueno, "   ")
    with pytest.raises(ValidationError):
        servicios.comentar(actividad, dueno, "x" * (servicios.MAX_TEXTO_COMENTARIO + 1))
    servicios.comentar(actividad, dueno, "x" * servicios.MAX_TEXTO_COMENTARIO)


def test_un_no_miembro_no_comenta(actividad, crear_usuario):
    with pytest.raises(PermisoDenegado):
        servicios.comentar(actividad, crear_usuario(), "hola")


def test_solo_el_autor_edita_y_queda_marcado(actividad, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    c = servicios.comentar(actividad, luis, "primero")
    with pytest.raises(PermisoDenegado):
        servicios.editar_comentario(c, dueno, "cambiado por el dueño")
    servicios.editar_comentario(c, luis, "primero")  # igual: no cuenta como editado
    assert c.editado_en is None
    servicios.editar_comentario(c, luis, "corregido")
    c.refresh_from_db()
    assert c.texto == "corregido" and c.editado_en is not None


def test_borra_el_autor_o_el_dueno(actividad, dueno, crear_usuario, agregar_miembro):
    luis, ana = crear_usuario(), crear_usuario()
    agregar_miembro(luis)
    agregar_miembro(ana)
    de_luis = servicios.comentar(actividad, luis, "de Luis")
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_comentario(de_luis, ana)
    servicios.eliminar_comentario(de_luis, dueno)
    de_ana = servicios.comentar(actividad, ana, "de Ana")
    servicios.eliminar_comentario(de_ana, ana)
    assert not Comentario.objects.exists()


def test_pizarra_archivada_no_admite_comentarios(actividad, dueno, pizarra):
    c = servicios.comentar(actividad, dueno, "antes de archivar")
    pizarras.archivar(pizarra, dueno)
    with pytest.raises(PermisoDenegado):
        servicios.comentar(actividad, dueno, "después")
    with pytest.raises(PermisoDenegado):
        servicios.editar_comentario(c, dueno, "después")
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_comentario(c, dueno)


def test_borrar_la_cuenta_conserva_el_comentario(actividad, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    c = servicios.comentar(actividad, luis, "me voy")
    luis.delete()
    c.refresh_from_db()
    assert c.autor is None and c.texto == "me voy"


def test_se_borran_con_la_actividad(actividad, dueno):
    servicios.comentar(actividad, dueno, "a")
    servicios.eliminar_actividad(actividad, dueno)
    assert not Comentario.objects.exists()
