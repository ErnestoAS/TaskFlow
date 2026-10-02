import pytest
from django.core.exceptions import ValidationError

from apps.proyectos import servicios as proyectos
from apps.proyectos.servicios import PermisoDenegado
from apps.tarjetas import servicios
from apps.tarjetas.models import CambioEstatus, Tarjeta

pytestmark = pytest.mark.django_db


def test_crear_tarjeta_registra_la_creacion(proyecto, dueno):
    t = servicios.crear_tarjeta(
        proyecto, dueno, titulo=" Reservar auditorio ", descripcion="Para el evento"
    )
    assert t.titulo == "Reservar auditorio" and t.estatus == "pendiente"
    assert list(t.asignados.all()) == [] and list(t.tipos.all()) == []  # ambos opcionales
    (cambio,) = t.cambios_estatus.all()
    assert (cambio.estatus_anterior, cambio.estatus_nuevo, cambio.usuario) == (
        "",
        "pendiente",
        dueno,
    )


def test_titulo_y_descripcion_son_obligatorios(proyecto, dueno):
    with pytest.raises(ValidationError) as e:
        servicios.crear_tarjeta(proyecto, dueno, titulo=" ", descripcion="")
    assert set(e.value.message_dict) == {"titulo", "descripcion"}


def test_solo_se_asigna_a_miembros_y_tipos_del_proyecto(proyecto, dueno, crear_usuario):
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(
            proyecto, dueno, titulo="a", descripcion="b", asignados=[crear_usuario()]
        )
    otro = proyectos.crear_proyecto(dueno, "Otro")
    tipo_ajeno = proyectos.crear_tipo(otro, dueno, nombre="Ajeno", color="#000000")
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b", tipos=[tipo_ajeno])


def test_varios_tipos_y_asignados(proyecto, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t1 = proyectos.crear_tipo(proyecto, dueno, nombre="Logística", color="#f08c00")
    t2 = proyectos.crear_tipo(proyecto, dueno, nombre="Urgente", color="#c92a2a")
    t = servicios.crear_tarjeta(
        proyecto, dueno, titulo="a", descripcion="b", asignados=[dueno, luis], tipos=[t1, t2]
    )
    assert set(t.asignados.all()) == {dueno, luis} and set(t.tipos.all()) == {t1, t2}


def test_cada_permiso_se_respeta(proyecto, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis, crear=False, editar=False, cambiar_estatus=False, eliminar=False)
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    with pytest.raises(PermisoDenegado):
        servicios.crear_tarjeta(proyecto, luis, titulo="a", descripcion="b")
    with pytest.raises(PermisoDenegado):
        servicios.editar_tarjeta(t, luis, titulo="c")
    with pytest.raises(PermisoDenegado):
        servicios.cambiar_estatus(t, luis, "en_curso")
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_tarjeta(t, luis)
    proyectos.cambiar_permisos(
        proyecto, dueno, luis, crear=True, editar=True, cambiar_estatus=True, eliminar=True
    )
    servicios.crear_tarjeta(proyecto, luis, titulo="a", descripcion="b")
    servicios.editar_tarjeta(t, luis, titulo="c")
    servicios.cambiar_estatus(t, luis, "en_curso")
    servicios.eliminar_tarjeta(t, luis)
    assert not Tarjeta.objects.filter(pk=t.pk).exists()


def test_un_no_miembro_no_toca_tarjetas(proyecto, dueno, crear_usuario):
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    ajeno = crear_usuario()
    with pytest.raises(PermisoDenegado):
        servicios.cambiar_estatus(t, ajeno, "finalizada")


def test_el_historial_registra_idas_y_vueltas(proyecto, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    servicios.cambiar_estatus(t, luis, "en_curso")
    servicios.cambiar_estatus(t, dueno, "finalizada")
    servicios.cambiar_estatus(t, luis, "en_curso")  # se reabre: permitido (§4.5)
    servicios.cambiar_estatus(t, luis, "en_curso")  # sin cambio: no deja fila
    pasos = list(
        t.cambios_estatus.order_by("fecha", "id").values_list(
            "estatus_anterior", "estatus_nuevo", "usuario"
        )
    )
    assert pasos == [
        ("", "pendiente", dueno.pk),
        ("pendiente", "en_curso", luis.pk),
        ("en_curso", "finalizada", dueno.pk),
        ("finalizada", "en_curso", luis.pk),
    ]
    t.refresh_from_db()
    assert t.estatus == "en_curso"


def test_estatus_invalido(proyecto, dueno):
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    with pytest.raises(ValidationError):
        servicios.cambiar_estatus(t, dueno, "archivada")


def test_proyecto_archivado_no_admite_cambios(proyecto, dueno):
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    proyectos.archivar(proyecto, dueno)
    with pytest.raises(PermisoDenegado):
        servicios.cambiar_estatus(t, dueno, "en_curso")
    with pytest.raises(PermisoDenegado):
        servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")


def test_borrar_la_cuenta_conserva_el_historial(proyecto, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    servicios.cambiar_estatus(t, luis, "en_curso")
    luis.delete()
    cambio = CambioEstatus.objects.get(tarjeta=t, estatus_nuevo="en_curso")
    assert cambio.usuario is None


def test_editar_no_toca_el_estatus(proyecto, dueno):
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    with pytest.raises(ValidationError):
        servicios.editar_tarjeta(t, dueno, estatus="finalizada")


def test_prioridad_por_omision_y_editable(proyecto, dueno):
    t = servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b")
    assert t.prioridad == "media"
    servicios.editar_tarjeta(t, dueno, prioridad="urgente")
    t.refresh_from_db()
    assert t.prioridad == "urgente"
    with pytest.raises(ValidationError):
        servicios.editar_tarjeta(t, dueno, prioridad="altisima")
    with pytest.raises(ValidationError):
        servicios.crear_tarjeta(proyecto, dueno, titulo="a", descripcion="b", prioridad="nula")
