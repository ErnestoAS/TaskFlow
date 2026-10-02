"""
Reglas de las cuentas: códigos por correo para verificar la cuenta y recuperar la contraseña (§4.3).

La API solo traduce peticiones a estas funciones. `ValidationError` → 400 con el mensaje por campo.

Un código es de 6 dígitos, vence a los `VIGENCIA_CODIGO`, admite `MAX_INTENTOS_CODIGO` intentos y
solo vale el más reciente de cada propósito. Con 5 intentos por código, un minuto entre envíos y
`MAX_ENVIOS_POR_HORA`, adivinar uno de un millón no es práctico.
"""

import secrets
from datetime import timedelta

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import CodigoCorreo, Usuario

VIGENCIA_CODIGO = timedelta(minutes=15)
MAX_INTENTOS_CODIGO = 5
ESPERA_ENTRE_ENVIOS = timedelta(minutes=1)
MAX_ENVIOS_POR_HORA = 5

# Mismo mensaje para código equivocado, vencido o correo sin cuenta: no revela qué cuentas existen.
CODIGO_INVALIDO = "El código no es válido o ya venció. Pide uno nuevo."


def _hash(usuario: Usuario, proposito: str, codigo: str) -> str:
    return salted_hmac(f"taskflow.codigo.{proposito}", f"{usuario.pk}:{codigo}").hexdigest()


def _enviar_correo(usuario: Usuario, proposito: str, codigo: str) -> None:
    contexto = {
        "usuario": usuario,
        "codigo": codigo,
        "minutos": int(VIGENCIA_CODIGO.total_seconds() // 60),
    }
    plantilla = f"usuarios/correos/{proposito}"
    asunto = render_to_string(f"{plantilla}_asunto.txt", contexto).strip()
    send_mail(asunto, render_to_string(f"{plantilla}.txt", contexto), None, [usuario.email])


def enviar_codigo(usuario: Usuario, proposito: str) -> None:
    """Genera un código nuevo (el anterior deja de valer) y lo manda al correo de la cuenta."""
    ahora = timezone.now()
    recientes = usuario.codigos.filter(
        proposito=proposito, creado_en__gte=ahora - timedelta(hours=1)
    )
    ultimo = recientes.first()
    if ultimo and ultimo.creado_en > ahora - ESPERA_ENTRE_ENVIOS:
        raise ValidationError("Espera un minuto antes de pedir otro código.")
    if recientes.count() >= MAX_ENVIOS_POR_HORA:
        raise ValidationError("Pediste demasiados códigos. Inténtalo dentro de una hora.")
    codigo = f"{secrets.randbelow(10**6):06d}"
    CodigoCorreo.objects.create(
        usuario=usuario, proposito=proposito, codigo_hash=_hash(usuario, proposito, codigo)
    )
    transaction.on_commit(lambda: _enviar_correo(usuario, proposito, codigo))


def _usar_codigo(usuario: Usuario, proposito: str, codigo: str) -> None:
    """Valida el código más reciente; si es correcto, borra todos los de ese propósito.

    El intento fallido se guarda en su propia transacción, antes de lanzar el error: si quien
    llama envolviera todo en `atomic`, el contador se desharía junto con el error.
    """
    codigo = (codigo or "").strip()
    with transaction.atomic():
        vigente = (
            usuario.codigos.select_for_update()
            .filter(proposito=proposito, creado_en__gt=timezone.now() - VIGENCIA_CODIGO)
            .first()
        )
        valido = (
            vigente is not None
            and vigente.intentos < MAX_INTENTOS_CODIGO
            and constant_time_compare(vigente.codigo_hash, _hash(usuario, proposito, codigo))
        )
        if valido:
            usuario.codigos.filter(proposito=proposito).delete()
        elif vigente is not None:
            vigente.intentos += 1
            vigente.save(update_fields=["intentos"])
    if not valido:
        raise ValidationError({"codigo": CODIGO_INVALIDO})


def _cuenta(correo: str) -> Usuario | None:
    correo = (correo or "").strip()
    return Usuario.objects.filter(email__iexact=correo, is_active=True).first() if correo else None


def marcar_verificado(usuario: Usuario) -> None:
    if usuario.correo_verificado_en is None:
        usuario.correo_verificado_en = timezone.now()
        usuario.save(update_fields=["correo_verificado_en", "actualizado_en"])


def pedir_verificacion(correo: str) -> None:
    """Reenvía el código de verificación. Calla si no hay cuenta pendiente con ese correo."""
    usuario = _cuenta(correo)
    if usuario and not usuario.correo_verificado:
        enviar_codigo(usuario, CodigoCorreo.Proposito.VERIFICAR)


def verificar_correo(correo: str, codigo: str) -> Usuario:
    usuario = _cuenta(correo)
    if usuario is None:
        raise ValidationError({"codigo": CODIGO_INVALIDO})
    if not usuario.correo_verificado:
        _usar_codigo(usuario, CodigoCorreo.Proposito.VERIFICAR, codigo)
        marcar_verificado(usuario)
    return usuario


def pedir_recuperacion(correo: str) -> None:
    """Manda el código para cambiar la contraseña. Calla si no hay cuenta con ese correo."""
    usuario = _cuenta(correo)
    if usuario:
        enviar_codigo(usuario, CodigoCorreo.Proposito.RECUPERAR)


def restablecer_password(correo: str, codigo: str, nueva: str) -> Usuario:
    """Cambia la contraseña con el código. También verifica el correo: el código llegó ahí."""
    usuario = _cuenta(correo)
    if usuario is None:
        raise ValidationError({"codigo": CODIGO_INVALIDO})
    try:
        validate_password(nueva, usuario)
    except ValidationError as e:
        raise ValidationError({"password": e.messages}) from e
    _usar_codigo(usuario, CodigoCorreo.Proposito.RECUPERAR, codigo)
    usuario.set_password(nueva)
    usuario.save(update_fields=["password", "actualizado_en"])
    marcar_verificado(usuario)
    return usuario
