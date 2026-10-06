"""
Pizarras, sus miembros, invitaciones, listas y tipos de tarjeta (§4.5 y §4.6 de la propuesta).

Una pizarra (antes «proyecto», renombrado el 2026-10-05) agrupa listas con nombre libre, y las
listas, tarjetas. Las reglas de negocio (quién puede qué) viven en `servicios.py`, no aquí: los
modelos solo guardan datos y las restricciones que la base de datos sí puede garantizar.
"""

import secrets

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import TimeStampedModel

# Los seis permisos que el dueño concede a cada miembro. El nombre es el sufijo del campo
# `puede_<permiso>` de MiembroPizarra; el dueño siempre los tiene todos.
PERMISOS = ("crear", "editar", "mover", "eliminar", "gestionar_listas", "gestionar_tipos")

# Listas con las que nace una pizarra (§4.6): (nombre, es_cierre).
LISTAS_INICIALES = (("Pendiente", False), ("En curso", False), ("Finalizada", True))

validar_color = RegexValidator(
    r"^#[0-9a-f]{6}$", "El color debe tener el formato #rrggbb (p. ej. #3b5bdb)."
)


class PizarraQuerySet(models.QuerySet):
    def de_usuario(self, usuario):
        """Pizarras de las que `usuario` es miembro (incluye las que es dueño)."""
        return self.filter(miembros__usuario=usuario)

    def activas(self):
        return self.filter(archivada_en__isnull=True)

    def archivadas(self):
        return self.filter(archivada_en__isnull=False)


class Pizarra(TimeStampedModel):
    nombre = models.CharField("nombre", max_length=150)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        on_delete=models.PROTECT,
        related_name="pizarras_creadas",
        help_text="Quién la creó. El dueño actual está en sus miembros (puede haber cambiado).",
    )
    archivada_en = models.DateTimeField(
        "archivada en",
        null=True,
        blank=True,
        help_text="Vacío = activa. Archivada = solo lectura para todos sus miembros.",
    )

    objects = PizarraQuerySet.as_manager()

    class Meta:
        verbose_name = "pizarra"
        verbose_name_plural = "pizarras"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def archivada(self) -> bool:
        return self.archivada_en is not None

    @property
    def dueno(self):
        membresia = self.miembros.filter(rol=MiembroPizarra.Rol.DUENO).select_related("usuario")
        return membresia.first().usuario if membresia.exists() else None


class MiembroPizarra(models.Model):
    class Rol(models.TextChoices):
        DUENO = "dueno", "Dueño"
        MIEMBRO = "miembro", "Miembro"

    pizarra = models.ForeignKey(
        Pizarra, verbose_name="pizarra", on_delete=models.CASCADE, related_name="miembros"
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        on_delete=models.CASCADE,
        related_name="membresias",
    )
    rol = models.CharField("rol", max_length=10, choices=Rol.choices, default=Rol.MIEMBRO)
    # Permisos sobre las tarjetas y la estructura de la pizarra. Para el dueño se ignoran: puede
    # todo. Los valores por omisión son los que recibe quien acepta una invitación.
    puede_crear = models.BooleanField("puede crear tarjetas", default=True)
    puede_editar = models.BooleanField("puede editar tarjetas", default=True)
    puede_mover = models.BooleanField("puede mover tarjetas", default=True)
    puede_eliminar = models.BooleanField("puede eliminar tarjetas", default=False)
    puede_gestionar_listas = models.BooleanField("puede gestionar listas", default=False)
    puede_gestionar_tipos = models.BooleanField("puede gestionar tipos", default=False)
    unido_en = models.DateTimeField("unido en", auto_now_add=True)

    class Meta:
        verbose_name = "miembro"
        verbose_name_plural = "miembros"
        ordering = ["rol", "usuario__email"]  # el dueño primero ("dueno" < "miembro")
        constraints = [
            models.UniqueConstraint(fields=["pizarra", "usuario"], name="miembro_unico"),
            # Un solo dueño por pizarra. Transferir = bajar al dueño actual y luego subir al
            # nuevo, en ese orden y en una transacción (servicios.transferir).
            models.UniqueConstraint(
                fields=["pizarra"], condition=Q(rol="dueno"), name="pizarra_un_solo_dueno"
            ),
            models.CheckConstraint(
                condition=Q(rol__in=["dueno", "miembro"]), name="miembro_rol_valido"
            ),
        ]

    def __str__(self):
        return f"{self.usuario} en {self.pizarra} ({self.get_rol_display()})"

    @property
    def es_dueno(self) -> bool:
        return self.rol == self.Rol.DUENO

    def puede(self, permiso: str) -> bool:
        if permiso not in PERMISOS:
            raise ValueError(f"Permiso desconocido: {permiso}")
        return self.es_dueno or getattr(self, f"puede_{permiso}")


def generar_token() -> str:
    return secrets.token_urlsafe(32)


class Invitacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        ACEPTADA = "aceptada", "Aceptada"
        CANCELADA = "cancelada", "Cancelada"

    pizarra = models.ForeignKey(
        Pizarra, verbose_name="pizarra", on_delete=models.CASCADE, related_name="invitaciones"
    )
    correo = models.EmailField("correo")
    invitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="invitada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitaciones_enviadas",
    )
    token = models.CharField(
        "token", max_length=64, unique=True, default=generar_token, editable=False
    )
    estado = models.CharField(
        "estado", max_length=10, choices=Estado.choices, default=Estado.PENDIENTE
    )
    creada_en = models.DateTimeField("creada en", auto_now_add=True)
    enviada_en = models.DateTimeField("último envío", default=timezone.now)
    veces_enviada = models.PositiveSmallIntegerField("veces enviada", default=1)
    respondida_en = models.DateTimeField("respondida en", null=True, blank=True)
    aceptada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="aceptada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitaciones_aceptadas",
    )

    class Meta:
        verbose_name = "invitación"
        verbose_name_plural = "invitaciones"
        ordering = ["-creada_en"]
        constraints = [
            # Una sola invitación pendiente por pizarra y correo. Sin vencimiento (decidido
            # 2026-10-01): queda pendiente hasta que se acepta o el dueño la cancela.
            models.UniqueConstraint(
                "pizarra",
                Lower("correo"),
                condition=Q(estado="pendiente"),
                name="invitacion_pendiente_unica",
            ),
        ]

    def __str__(self):
        return f"{self.correo} a {self.pizarra} ({self.get_estado_display()})"

    def save(self, *args, **kwargs):
        self.correo = (self.correo or "").strip().lower()
        super().save(*args, **kwargs)


class Lista(TimeStampedModel):
    """
    Columna de una pizarra con nombre libre (§4.6), en lugar de los tres estatus fijos.
    `es_cierre`: lo que llega aquí cuenta como terminado (no sale vencido ni en «Mis tarjetas»).
    """

    pizarra = models.ForeignKey(
        Pizarra, verbose_name="pizarra", on_delete=models.CASCADE, related_name="listas"
    )
    nombre = models.CharField("nombre", max_length=50)
    posicion = models.PositiveIntegerField("posición", default=0)
    es_cierre = models.BooleanField(
        "lista de cierre",
        default=False,
        help_text="Lo que llega aquí cuenta como terminado: no sale vencido ni en «Mis tarjetas».",
    )

    class Meta:
        verbose_name = "lista"
        verbose_name_plural = "listas"
        ordering = ["posicion", "id"]
        constraints = [
            # En «Mover a» dos listas con el mismo nombre serían indistinguibles.
            models.UniqueConstraint(
                "pizarra", Lower("nombre"), name="lista_nombre_unico_en_pizarra"
            ),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip()
        super().save(*args, **kwargs)


class TipoTarjeta(TimeStampedModel):
    pizarra = models.ForeignKey(
        Pizarra, verbose_name="pizarra", on_delete=models.CASCADE, related_name="tipos"
    )
    nombre = models.CharField("nombre", max_length=50)
    descripcion = models.TextField("descripción", blank=True)
    # Único color que viene del usuario: se valida aquí y en la base de datos (§4.5).
    color = models.CharField("color", max_length=7, validators=[validar_color])

    class Meta:
        verbose_name = "tipo de tarjeta"
        verbose_name_plural = "tipos de tarjeta"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                "pizarra", Lower("nombre"), name="tipo_nombre_unico_en_pizarra"
            ),
            models.CheckConstraint(
                condition=Q(color__regex=r"^#[0-9a-f]{6}$"), name="tipo_color_valido"
            ),
        ]

    def __str__(self):
        return self.nombre

    def save(self, *args, **kwargs):
        self.nombre = (self.nombre or "").strip()
        self.color = (self.color or "").strip().lower()
        super().save(*args, **kwargs)
