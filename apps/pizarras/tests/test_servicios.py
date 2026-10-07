import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.pizarras import servicios
from apps.pizarras.models import Invitacion, Lista, MiembroPizarra, Pizarra, TipoActividad
from apps.pizarras.servicios import PermisoDenegado

pytestmark = pytest.mark.django_db


# --- pizarras ----------------------------------------------------------------------------------


def test_quien_crea_la_pizarra_es_su_dueno(pizarra, dueno):
    m = MiembroPizarra.objects.get(pizarra=pizarra)
    assert m.usuario == dueno and m.es_dueno
    assert pizarra.dueno == dueno
    assert list(Pizarra.objects.de_usuario(dueno)) == [pizarra]


def test_la_pizarra_nace_sin_listas(dueno):
    # Cada quien arma sus listas (2026-10-06): no se imponen «Pendiente / En curso / Finalizada».
    p = servicios.crear_pizarra(dueno, "Nueva")
    assert not p.listas.exists()


def test_un_no_miembro_no_ve_la_pizarra(pizarra, crear_usuario):
    ajeno = crear_usuario()
    assert not Pizarra.objects.de_usuario(ajeno).exists()
    with pytest.raises(PermisoDenegado):
        servicios.exigir_miembro(pizarra, ajeno)


def test_la_bd_no_permite_dos_duenos(pizarra, crear_usuario):
    with pytest.raises(IntegrityError), transaction.atomic():
        MiembroPizarra.objects.create(pizarra=pizarra, usuario=crear_usuario(), rol="dueno")


def test_transferir_baja_al_dueno_con_todos_los_permisos(
    pizarra, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    servicios.transferir(pizarra, dueno, luis)
    assert pizarra.dueno == luis
    anterior = MiembroPizarra.objects.get(pizarra=pizarra, usuario=dueno)
    assert anterior.rol == "miembro"
    assert all(anterior.puede(p) for p in servicios.PERMISOS)


def test_solo_el_dueno_transfiere_salvo_un_administrador(
    pizarra, dueno, crear_usuario, agregar_miembro
):
    luis, admin = crear_usuario(), crear_usuario(is_staff=True)
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.transferir(pizarra, luis, luis)
    servicios.transferir(pizarra, admin, luis, como_administrador=True)
    assert pizarra.dueno == luis


def test_no_se_transfiere_a_quien_no_es_miembro(pizarra, dueno, crear_usuario):
    with pytest.raises(ValidationError):
        servicios.transferir(pizarra, dueno, crear_usuario())


def test_archivada_es_solo_lectura_y_se_restaura(pizarra, dueno):
    servicios.archivar(pizarra, dueno)
    assert pizarra.archivada
    with pytest.raises(PermisoDenegado):
        servicios.crear_tipo(pizarra, dueno, nombre="Logística", color="#f08c00")
    with pytest.raises(PermisoDenegado):
        servicios.crear_lista(pizarra, dueno, "Ideas")
    servicios.restaurar(pizarra, dueno)
    assert not pizarra.archivada
    servicios.crear_tipo(pizarra, dueno, nombre="Logística", color="#f08c00")


def test_solo_el_dueno_archiva_y_elimina(pizarra, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis, eliminar=True)
    with pytest.raises(PermisoDenegado):
        servicios.archivar(pizarra, luis)
    with pytest.raises(PermisoDenegado):
        servicios.eliminar_pizarra(pizarra, luis)


def test_eliminar_pizarra_borra_sus_actividades_y_listas(pizarra, dueno):
    from apps.actividades.models import Actividad
    from apps.actividades.servicios import crear_actividad

    crear_actividad(pizarra, dueno, titulo="Una")
    servicios.eliminar_pizarra(pizarra, dueno)
    assert not Actividad.objects.exists() and not Lista.objects.exists()


# --- miembros y permisos -----------------------------------------------------------------------


def test_permisos_por_omision_de_un_miembro_nuevo(pizarra, crear_usuario, agregar_miembro):
    m = agregar_miembro(crear_usuario())
    assert m.puede("crear") and m.puede("editar") and m.puede("mover")
    assert not m.puede("eliminar")
    assert not m.puede("gestionar_listas") and not m.puede("gestionar_tipos")


def test_el_dueno_cambia_permisos_y_nadie_mas(pizarra, dueno, crear_usuario, agregar_miembro):
    luis, maria = crear_usuario(), crear_usuario()
    agregar_miembro(luis)
    agregar_miembro(maria)
    servicios.cambiar_permisos(pizarra, dueno, luis, eliminar=True, crear=False)
    m = MiembroPizarra.objects.get(pizarra=pizarra, usuario=luis)
    assert m.puede_eliminar and not m.puede_crear
    with pytest.raises(PermisoDenegado):
        servicios.cambiar_permisos(pizarra, luis, maria, eliminar=True)
    with pytest.raises(ValidationError):
        servicios.cambiar_permisos(pizarra, dueno, dueno, eliminar=False)
    with pytest.raises(ValidationError):
        servicios.cambiar_permisos(pizarra, dueno, luis, cambiar_estatus=True)  # ya no existe


def test_quitar_miembro_lo_desasigna(pizarra, dueno, crear_usuario, agregar_miembro):
    from apps.actividades.servicios import crear_actividad

    luis = crear_usuario()
    agregar_miembro(luis)
    t = crear_actividad(pizarra, dueno, titulo="Una", asignados=[luis, dueno])
    servicios.quitar_miembro(pizarra, dueno, luis)
    assert servicios.membresia(pizarra, luis) is None
    assert list(t.asignados.all()) == [dueno]


def test_el_dueno_no_puede_salir_ni_ser_quitado(pizarra, dueno):
    with pytest.raises(ValidationError):
        servicios.salir(pizarra, dueno)
    with pytest.raises(ValidationError):
        servicios.quitar_miembro(pizarra, dueno, dueno)


def test_un_miembro_puede_salir(pizarra, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    servicios.salir(pizarra, luis)
    assert servicios.membresia(pizarra, luis) is None


# --- invitaciones ------------------------------------------------------------------------------


def test_invitar_envia_correo_con_enlace(
    pizarra, dueno, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        inv = servicios.invitar(pizarra, dueno, "  Sofia@Ejemplo.MX ")
    assert inv.correo == "sofia@ejemplo.mx" and inv.estado == "pendiente"
    assert len(mailoutbox) == 1
    assert mailoutbox[0].to == ["sofia@ejemplo.mx"]
    assert "la pizarra «Semana de la Ciencia»" in mailoutbox[0].body
    assert f"https://ejemplo.mx/taskflow/app/#/invitacion/{inv.token}" in mailoutbox[0].body


def test_solo_el_dueno_invita(pizarra, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.invitar(pizarra, luis, "otra@ejemplo.mx")


def test_no_se_invita_dos_veces_ni_a_un_miembro(pizarra, dueno, crear_usuario, agregar_miembro):
    agregar_miembro(crear_usuario("luis@ejemplo.mx"))
    with pytest.raises(ValidationError):
        servicios.invitar(pizarra, dueno, "LUIS@ejemplo.mx")
    servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    with pytest.raises(ValidationError):
        servicios.invitar(pizarra, dueno, "Sofia@ejemplo.mx")


def test_reenviar_cuenta_envios_y_tiene_tope(
    pizarra, dueno, mailoutbox, django_capture_on_commit_callbacks
):
    inv = servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    with django_capture_on_commit_callbacks(execute=True):
        servicios.reenviar_invitacion(inv, dueno)
    assert inv.veces_enviada == 2 and len(mailoutbox) == 1
    Invitacion.objects.filter(pk=inv.pk).update(veces_enviada=servicios.MAX_ENVIOS_INVITACION)
    inv.refresh_from_db()
    with pytest.raises(ValidationError):
        servicios.reenviar_invitacion(inv, dueno)


def test_aceptar_invitacion_da_permisos_por_omision(pizarra, dueno, crear_usuario):
    inv = servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    sofia = crear_usuario("SOFIA@ejemplo.mx")
    m = servicios.aceptar_invitacion(inv.token, sofia)
    inv.refresh_from_db()
    assert inv.estado == "aceptada" and inv.aceptada_por == sofia
    assert m.puede("crear") and m.puede("mover") and not m.puede("eliminar")
    with pytest.raises(ValidationError):  # ya no está pendiente
        servicios.aceptar_invitacion(inv.token, sofia)


def test_la_invitacion_solo_la_acepta_el_correo_invitado(pizarra, dueno, crear_usuario):
    inv = servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    with pytest.raises(PermisoDenegado):
        servicios.aceptar_invitacion(inv.token, crear_usuario("otra@ejemplo.mx"))


def test_invitacion_cancelada_no_se_acepta(pizarra, dueno, crear_usuario):
    inv = servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")
    servicios.cancelar_invitacion(inv, dueno)
    with pytest.raises(ValidationError):
        servicios.aceptar_invitacion(inv.token, crear_usuario("sofia@ejemplo.mx"))
    servicios.invitar(pizarra, dueno, "sofia@ejemplo.mx")  # se puede volver a invitar


# --- listas ------------------------------------------------------------------------------------


def test_crear_lista_la_pone_al_final_y_valida_el_nombre(pizarra, dueno):
    ideas = servicios.crear_lista(pizarra, dueno, "  Ideas ")
    assert (ideas.nombre, ideas.posicion) == ("Ideas", 3)
    with pytest.raises(ValidationError):
        servicios.crear_lista(pizarra, dueno, "IDEAS")  # mismo nombre sin distinguir mayúsculas
    with pytest.raises(ValidationError):
        servicios.crear_lista(pizarra, dueno, "  ")
    otra = servicios.crear_pizarra(dueno, "Otra")
    servicios.crear_lista(otra, dueno, "Ideas")  # en otra pizarra sí


def test_renombrar_lista(pizarra, dueno, listas):
    en_curso = listas["En curso"]
    servicios.editar_lista(en_curso, dueno, nombre="Haciéndose")
    en_curso.refresh_from_db()
    assert en_curso.nombre == "Haciéndose"
    with pytest.raises(ValidationError):
        servicios.editar_lista(en_curso, dueno, nombre="pendiente")
    with pytest.raises(ValidationError):
        servicios.editar_lista(en_curso, dueno, posicion=0)


def test_ordenar_listas_exige_todas(pizarra, dueno, listas):
    ids = [listas["Finalizada"].pk, listas["Pendiente"].pk, listas["En curso"].pk]
    servicios.ordenar_listas(pizarra, dueno, ids)
    assert list(pizarra.listas.values_list("nombre", flat=True)) == [
        "Finalizada",
        "Pendiente",
        "En curso",
    ]
    with pytest.raises(ValidationError):
        servicios.ordenar_listas(pizarra, dueno, ids[:2])


def test_solo_se_elimina_una_lista_vacia(pizarra, dueno, listas):
    from apps.actividades.servicios import crear_actividad

    crear_actividad(pizarra, dueno, titulo="Una", lista=listas["En curso"])
    with pytest.raises(ValidationError):
        servicios.eliminar_lista(listas["En curso"], dueno)
    servicios.eliminar_lista(listas["Finalizada"], dueno)
    assert not Lista.objects.filter(pk=listas["Finalizada"].pk).exists()


def test_gestionar_listas_requiere_permiso(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.crear_lista(pizarra, luis, "Ideas")
    servicios.cambiar_permisos(pizarra, dueno, luis, gestionar_listas=True)
    servicios.crear_lista(pizarra, luis, "Ideas")


# --- tipos de actividad --------------------------------------------------------------------------


def test_crear_tipo_normaliza_y_valida(pizarra, dueno):
    t = servicios.crear_tipo(pizarra, dueno, nombre=" Logística ", color="#F08C00", descripcion="")
    assert (t.nombre, t.color) == ("Logística", "#f08c00")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(pizarra, dueno, nombre="logística", color="#000000")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(pizarra, dueno, nombre="Difusión", color="rojo")
    with pytest.raises(ValidationError):
        servicios.crear_tipo(pizarra, dueno, nombre="  ", color="#000000")


def test_el_mismo_nombre_de_tipo_vale_en_otra_pizarra(pizarra, dueno):
    otra = servicios.crear_pizarra(dueno, "Otra")
    servicios.crear_tipo(pizarra, dueno, nombre="Logística", color="#f08c00")
    servicios.crear_tipo(otra, dueno, nombre="Logística", color="#f08c00")
    assert TipoActividad.objects.count() == 2


def test_gestionar_tipos_requiere_permiso(pizarra, dueno, crear_usuario, agregar_miembro):
    luis = crear_usuario()
    agregar_miembro(luis)
    with pytest.raises(PermisoDenegado):
        servicios.crear_tipo(pizarra, luis, nombre="Logística", color="#f08c00")
    servicios.cambiar_permisos(pizarra, dueno, luis, gestionar_tipos=True)
    t = servicios.crear_tipo(pizarra, luis, nombre="Logística", color="#f08c00")
    servicios.editar_tipo(t, luis, color="#123abc")
    assert TipoActividad.objects.get(pk=t.pk).color == "#123abc"


def test_eliminar_tipo_no_borra_actividades(pizarra, dueno):
    from apps.actividades.servicios import crear_actividad

    tipo = servicios.crear_tipo(pizarra, dueno, nombre="Urgente", color="#c92a2a")
    t = crear_actividad(pizarra, dueno, titulo="Una", tipos=[tipo])
    servicios.eliminar_tipo(tipo, dueno)
    t.refresh_from_db()
    assert list(t.tipos.all()) == []
