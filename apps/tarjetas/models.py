"""
Tarjetas: la unidad de trabajo de TaskFlow (§4.4 y §4.5 de la propuesta).

Cada tarjeta pertenece a un proyecto, tiene título, descripción, un estatus de tres valores, una
fecha de fin opcional, cero o más asignados (miembros del proyecto) y cero o más tipos (del mismo
proyecto). Cada cambio de estatus queda en `CambioEstatus`.

Las reglas (permisos, que los asignados sean miembros, que los tipos sean del proyecto) viven en
`servicios.py`: la base de datos no puede expresarlas.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Estatus(models.TextChoices):
    PENDIENTE = "pendiente", "Pendiente"
    EN_CURSO = "en_curso", "En curso"
    FINALIZADA = "finalizada", "Finalizada"


class Prioridad(models.TextChoices):
    """Fija para todos los proyectos (decidido 2026-10-01), a diferencia de los tipos."""

    BAJA = "baja", "Baja"
    MEDIA = "media", "Media"
    ALTA = "alta", "Alta"
    URGENTE = "urgente", "Urgente"


# Para ordenar de más a menos urgente sin depender del orden alfabético.
ORDEN_PRIORIDAD = {"urgente": 0, "alta": 1, "media": 2, "baja": 3}


class Tarjeta(TimeStampedModel):
    Estatus = Estatus  # Tarjeta.Estatus.PENDIENTE, como antes
    Prioridad = Prioridad

    proyecto = models.ForeignKey(
        "proyectos.Proyecto",
        verbose_name="proyecto",
        on_delete=models.CASCADE,
        related_name="tarjetas",
    )
    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción")
    estatus = models.CharField(
        "estatus",
        max_length=20,
        choices=Estatus.choices,
        default=Estatus.PENDIENTE,
        db_index=True,
    )
    prioridad = models.CharField(
        "prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    fecha_fin = models.DateField("fecha fin", null=True, blank=True)
    asignados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="asignados",
        related_name="tarjetas_asignadas",
        blank=True,
    )
    tipos = models.ManyToManyField(
        "proyectos.TipoTarjeta",
        verbose_name="tipos",
        related_name="tarjetas",
        blank=True,
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="tarjetas_creadas",
    )

    class Meta:
        verbose_name = "tarjeta"
        verbose_name_plural = "tarjetas"
        ordering = ["-creado_en"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(estatus__in=["pendiente", "en_curso", "finalizada"]),
                name="tarjeta_estatus_valido",
            ),
            models.CheckConstraint(
                condition=models.Q(prioridad__in=["baja", "media", "alta", "urgente"]),
                name="tarjeta_prioridad_valida",
            ),
        ]
        indexes = [models.Index(fields=["proyecto", "estatus"], name="tarjeta_proyecto_estatus")]

    def __str__(self):
        return self.titulo


class CambioEstatus(models.Model):
    """
    Historial de estatus (§4.5): quién, de qué estatus a cuál, fecha y hora. Solo se agregan
    filas; las escribe `servicios.cambiar_estatus` (y la creación de tarjetas y el admin) en la
    misma transacción que el cambio. `estatus_anterior` vacío = la creación de la tarjeta.
    """

    tarjeta = models.ForeignKey(
        Tarjeta, verbose_name="tarjeta", on_delete=models.CASCADE, related_name="cambios_estatus"
    )
    estatus_anterior = models.CharField(
        "estatus anterior", max_length=20, choices=Estatus.choices, blank=True
    )
    estatus_nuevo = models.CharField("estatus nuevo", max_length=20, choices=Estatus.choices)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cambios_estatus",
        help_text="Vacío si la cuenta se borró: el cambio se conserva («Usuario eliminado»).",
    )
    # default y no auto_now_add: la migración que siembra el historial de tarjetas existentes
    # necesita poner la fecha de creación de cada una.
    fecha = models.DateTimeField("fecha", default=timezone.now)

    class Meta:
        verbose_name = "cambio de estatus"
        verbose_name_plural = "historial de estatus"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["tarjeta", "-fecha"], name="cambio_tarjeta_fecha")]

    def __str__(self):
        de = self.get_estatus_anterior_display() or "creación"
        return f"{self.tarjeta}: {de} → {self.get_estatus_nuevo_display()}"
