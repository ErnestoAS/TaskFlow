import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.usuarios import servicios as su
from apps.usuarios.models import CodigoCorreo

pytestmark = pytest.mark.django_db
VERIFICAR = CodigoCorreo.Proposito.VERIFICAR


@pytest.fixture
def pendiente(crear_usuario):
    return crear_usuario("ana@ejemplo.mx", correo_verificado_en=None)


def _codigo(mailoutbox):
    return re.search(r"\b(\d{6})\b", mailoutbox[-1].body).group(1)


def _envejecer(usuario, **delta):
    """Mueve los códigos hacia atrás en el tiempo (para la espera entre envíos o el vencimiento)."""
    for c in usuario.codigos.all():
        c.creado_en -= timedelta(**delta)
        c.save(update_fields=["creado_en"])


def test_el_codigo_no_se_guarda_en_claro(pendiente, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    codigo = _codigo(mailoutbox)
    assert codigo not in pendiente.codigos.get().codigo_hash


def test_verificar_correo(pendiente, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    su.verificar_correo("ANA@ejemplo.mx", _codigo(mailoutbox))
    pendiente.refresh_from_db()
    assert pendiente.correo_verificado and not pendiente.codigos.exists()


def test_codigo_vencido(pendiente, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    _envejecer(pendiente, minutes=16)
    with pytest.raises(ValidationError):
        su.verificar_correo("ana@ejemplo.mx", _codigo(mailoutbox))


def test_tope_de_intentos(pendiente, mailoutbox, django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    malo = "000000" if _codigo(mailoutbox) != "000000" else "111111"
    for _ in range(su.MAX_INTENTOS_CODIGO):
        with pytest.raises(ValidationError):
            su.verificar_correo("ana@ejemplo.mx", malo)
    assert pendiente.codigos.get().intentos == su.MAX_INTENTOS_CODIGO
    # Agotados los intentos, ni el código correcto sirve.
    with pytest.raises(ValidationError):
        su.verificar_correo("ana@ejemplo.mx", _codigo(mailoutbox))


def test_solo_vale_el_codigo_mas_reciente(
    pendiente, mailoutbox, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    viejo = _codigo(mailoutbox)
    _envejecer(pendiente, minutes=2)
    with django_capture_on_commit_callbacks(execute=True):
        su.enviar_codigo(pendiente, VERIFICAR)
    nuevo = _codigo(mailoutbox)
    if viejo != nuevo:
        with pytest.raises(ValidationError):
            su.verificar_correo("ana@ejemplo.mx", viejo)
    su.verificar_correo("ana@ejemplo.mx", nuevo)


def test_espera_y_tope_de_envios(pendiente):
    su.enviar_codigo(pendiente, VERIFICAR)
    with pytest.raises(ValidationError, match="Espera un minuto"):
        su.enviar_codigo(pendiente, VERIFICAR)
    for _ in range(su.MAX_ENVIOS_POR_HORA - 1):
        _envejecer(pendiente, minutes=2)
        su.enviar_codigo(pendiente, VERIFICAR)
    _envejecer(pendiente, minutes=2)
    with pytest.raises(ValidationError, match="demasiados"):
        su.enviar_codigo(pendiente, VERIFICAR)


def test_correo_sin_cuenta_no_revela_nada(db):
    su.pedir_recuperacion("nadie@ejemplo.mx")  # No falla ni manda nada.
    with pytest.raises(ValidationError) as e:
        su.verificar_correo("nadie@ejemplo.mx", "123456")
    assert e.value.message_dict["codigo"] == [su.CODIGO_INVALIDO]


def test_cuenta_desactivada_no_recupera(crear_usuario, mailoutbox):
    crear_usuario("ana@ejemplo.mx", is_active=False)
    su.pedir_recuperacion("ana@ejemplo.mx")
    assert not mailoutbox


def test_nombre_completo_con_dos_apellidos(crear_usuario):
    u = crear_usuario(nombre="Ana", primer_apellido="López", segundo_apellido="Ramírez")
    assert u.nombre_completo == "Ana López Ramírez"
    u.segundo_apellido = ""
    assert u.nombre_completo == "Ana López"


def test_superusuario_queda_verificado(django_user_model):
    u = django_user_model.objects.create_superuser("admin@ejemplo.mx", "x")
    assert u.correo_verificado
    assert (
        django_user_model.objects.create_user("otra@ejemplo.mx", "x").correo_verificado_en is None
    )
    assert u.correo_verificado_en <= timezone.now()
