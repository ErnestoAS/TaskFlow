import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.proyectos import servicios
from apps.proyectos.models import Invitacion, MiembroProyecto, Proyecto, TipoTarjeta
from apps.proyectos.servicios import PermisoDenegado

pytestmark = pytest.mark.django_db


# --- proyectos ---------------------------------------------------------------------------------


def test_quien_crea_el_proyecto_es_su_dueno(proyecto, dueno):
    m = MiembroProyecto.objects.get(proyecto=proyecto)
    assert m.usuario == dueno and m.es_dueno
    assert proyecto.dueno == dueno
    assert list(Proyecto.objects.de_usuario(dueno)) == [proyecto]


def test_un_no_miembro_no_ve_el_proyecto(proyecto, crear_usuario):
    ajeno = crear_usuario()
    assert not Proyecto.objects.de_usuario(ajeno).exists()
    with pytest.raises(PermisoDenegado):
        servicios.exigir_miembro(proyecto, ajeno)


def test_la_bd_no_permite_dos_duenos(proyecto, crear_usuario):
    with pytest.raises(IntegrityError), transaction.atomic():
        MiembroProyecto.objects.create(proyecto=proyecto, usuario=crear_usuario(), rol="dueno")


def test_transferir_baja_al_dueno_con_todos_los_permisos(
    proyecto, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    servicios.transferir(proyecto, dueno, luis)
    assert proyecto.dueno == luis
    anterior = MiembroProyecto.objects.get(proyecto=proyecto, usuario=dueno)
    assert anterior.rol == "miembro"
    assert all(
        anterior.puede(p)
        for p in ("crear", "editar", "cambiar_estatus", "eliminar", "gestionar_tipos")
    )


def test_solo_el_dueno_transfiere_salvo_un_administrador(
    proyecto, dueno, crear_usuario, agregar_miembro
):
    luis, admin = crear_usuario(), crear_usuario(is_staff=True)
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.transferir(proyecto, luis, luis)
    servicios.transferir(proyecto, admin, luis, como_administrador=True)
    assert proyecto.dueno == luis


def test_no_se_transfiere_a_quien_no_es_miembro(proyecto, dueno, crear_usuario):
    with pytest.raises(ValidationError):
        servicios.transferir(proyecto, dueno, crear_usuario())


def test_archivado_es_solo_lectura_y_se_restaura(proyecto, dueno):
    servicios.archivar(proyecto, dueno)
    assert proyecto.archivado
    with pytest.raises(PermisoDenegado):
        servicios.crear_tipo(proyecto, dueno, nombre="Logística", color="#f08c00")
    servicios.restaurar(proyecto, dueno)
    assert not proyecto.archivado
    servicios.crear_tipo(proyecto, dueno, nombre="Logística", color="#f08c00")


def test_solo_el_dueno_archiva_y_elimina(proyecto, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis, eliminar=True)
    with pytest.raises(PermisoDenegado):
        servicios.archivar(proyecto, luis)
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_proyecto(proyecto, luis)


def test_eliminar_proyecto_borra_sus_tarjetas(proyecto, dueno):
    from apps.tarjetas.models import Tarjeta
    from apps.tarjetas.servicios import crear_tarjeta

    crear_tarjeta(proyecto, dueno, titulo="Una", descripcion="x")
    servicios.eliminar_proyecto(proyecto, dueno)
    assert not Tarjeta.objects.exists()


# --- miembros y permisos -----------------------------------------------------------------------


def test_permisos_por_omision_de_un_miembro_nuevo(proyecto, crear_usuario, agregar_miembro):
    m = agregar_miembro(crear_usuario())
    assert m.puede("crear") and m.puede("editar") and m.puede("cambiar_estatus")
    assert not m.puede("eliminar") and not m.puede("gestionar_tipos")


def test_el_dueno_cambia_permisos_y_nadie_mas(proyecto, dueno, crear_usuario, agregar_miembro):
    luis, maria = crear_usuario(), crear_usuario()
    agregar_miembro(luis)
    agregar_miembro(maria)
    servicios.cambiar_permisos(proyecto, dueno, luis, eliminar=True, crear=False)
    m = MiembroProyecto.objects.get(proyecto=proyecto, usuario=luis)
    assert m.puede_eliminar and not m.puede_crear
    with pytest.raises(PermisoDenegado):
        servicios.cambiar_permisos(proyecto, luis, maria, eliminar=True)
    with pytest.raises(ValidationError):
        servicios.cambiar_permisos(proyecto, dueno, dueno, eliminar=False)
    with pytest.raises(ValidationError):
        servicios.cambiar_permisos(proyecto, dueno, luis, volar=True)


def test_quitar_miembro_lo_desasigna(proyecto, dueno, crear_usuario, agregar_miembro):
    from apps.tarjetas.servicios import crear_tarjeta

    luis = crear_usuario()
    agregar_miembro(luis)
    t = crear_tarjeta(proyecto, dueno, titulo="Una", descripcion="x", asignados=[luis, dueno])
    servicios.quitar_miembro(proyecto, dueno, luis)
    assert servicios.membresia(proyecto, luis) is None
    assert list(t.asignados.all()) == [dueno]


def test_el_dueno_no_puede_salir_ni_ser_quitado(proyecto, dueno):
    with pytest.raises(ValidationError):
        servicios.salir(proyecto, dueno)
    with pytest.raises(ValidationError):
        servicios.quitar_miembro(proyecto, dueno, dueno)


def test_un_miembro_puede_salir(proyecto, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    servicios.salir(proyecto, luis)
    assert servicios.membresia(proyecto, luis) is None


# --- invitaciones ------------------------------------------------------------------------------


def test_invitar_envia_correo_con_enlace(
    proyecto, dueno, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        inv = servicios.invitar(proyecto, dueno, "  Sofia@Ejemplo.MX ")
    assert inv.correo == "sofia@ejemplo.mx" and inv.estado == "pendiente"
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["sofia@ejemplo.mx"]
    assert f"https://ejemplo.mx/taskflow/app/#/invitacion/{inv.token}" in mailoutbox[0].body


def test_solo_el_dueno_invita(proyecto, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.invitar(proyecto, luis, "otra@ejemplo.mx")


def test_no_se_invita_dos_veces_ni_a_un_miembro(proyecto, dueno, crear_usuario, agregar_miembro):
    agregar_miembro(crear_usuario("luis@ejemplo.mx"))
    with pytest.raises(ValidationError):
        servicios.invitar(proyecto, dueno, "LUIS@ejemplo.mx")
    servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    with pytest.raises(ValidationError):
        servicios.invitar(proyecto, dueno, "Sofia@ejemplo.mx")


def test_reenviar_cuenta_envios_y_tiene_tope(
    proyecto, dueno, mailoutbox, django_capture_on_commit_callbacks
):
    inv = servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    with django_capture_on_commit_callbacks(execute=True):
        servicios.reenviar_invitacion(inv, dueno)
    assert inv.veces_enviada == 2 and len(mailoutbox) == 1
    Invitacion.objects.filter(pk=inv.pk).update(veces_enviada=servicios.MAX_ENVIOS_INVITACION)
    inv.refresh_from_db()
    with pytest.raises(ValidationError):
        servicios.reenviar_invitacion(inv, dueno)


def test_aceptar_invitacion_da_permisos_por_omision(proyecto, dueno, crear_usuario):
    inv = servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    sofia = crear_usuario("SOFIA@ejemplo.mx")
    m = servicios.aceptar_invitacion(inv.token, sofia)
    inv.refresh_from_db()
    assert inv.estado == "aceptada" and inv.aceptada_por == sofia
    assert m.puede("crear") and not m.puede("eliminar")
    with pytest.raises(ValidationError):  # ya no está pendiente
        servicios.aceptar_invitacion(inv.token, sofia)


def test_la_invitacion_solo_la_acepta_el_correo_invitado(proyecto, dueno, crear_usuario):
    inv = servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    with pytest.raises(PermisoDenegado):
        servicios.aceptar_invitacion(inv.token, crear_usuario("otra@ejemplo.mx"))


def test_invitacion_cancelada_no_se_acepta(proyecto, dueno, crear_usuario):
    inv = servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")
    servicios.cancelar_invitacion(inv, dueno)
    with pytest.raises(ValidationError):
        servicios.aceptar_invitacion(inv.token, crear_usuario("sofia@ejemplo.mx"))
    servicios.invitar(proyecto, dueno, "sofia@ejemplo.mx")  # se puede volver a invitar


# --- tipos de tarjeta --------------------------------------------------------------------------


def test_crear_tipo_normaliza_y_valida(proyecto, dueno):
    t = servicios.crear_tipo(proyecto, dueno, nombre=" Logística ", color="#F08C00", descripcion="")
    assert (t.nombre, t.color) == ("Logística", "#f08c00")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(proyecto, dueno, nombre="logística", color="#000000")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(proyecto, dueno, nombre="Difusión", color="rojo")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(proyecto, dueno, nombre="  ", color="#000000")


def test_el_mismo_nombre_de_tipo_vale_en_otro_proyecto(proyecto, dueno):
    otro = servicios.crear_proyecto(dueno, "Otro")
    servicios.crear_tipo(proyecto, dueno, nombre="Logística", color="#f08c00")
    servicios.crear_tipo(otro, dueno, nombre="Logística", color="#f08c00")
    assert TipoTarjeta.objects.count() == 2


def test_gestionar_tipos_requiere_permiso(proyecto, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.crear_tipo(proyecto, luis, nombre="Logística", color="#f08c00")
    servicios.cambiar_permisos(proyecto, dueno, luis, gestionar_tipos=True)
    t = servicios.crear_tipo(proyecto, luis, nombre="Logística", color="#f08c00")
    servicios.editar_tipo(t, luis, color="#123abc")
    assert TipoTarjeta.objects.get(pk=t.pk).color == "#123abc"


def test_eliminar_tipo_no_borra_tarjetas(proyecto, dueno):
    from apps.tarjetas.servicios import crear_tarjeta

    tipo = servicios.crear_tipo(proyecto, dueno, nombre="Urgente", color="#c92a2a")
    t = crear_tarjeta(proyecto, dueno, titulo="Una", descripcion="x", tipos=[tipo])
    servicios.eliminar_tipo(tipo, dueno)
    t.refresh_from_db()
    assert list(t.tipos.all()) == []
