"""
Tarjetas: la unidad de trabajo de TaskFlow.

Cada tarjeta es una actividad con título, descripción, un estatus de tres valores y una fecha de
fin opcional. Puede asignarse a una o más personas.
"""

from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class Tarjeta(TimeStampedModel):
    class Estatus(models.TextChoices):
        PENDIENTE = "pendiente", "Pendiente"
        EN_CURSO = "en_curso", "En curso"
        FINALIZADA = "finalizada", "Finalizada"

    titulo = models.CharField("título", max_length=200)
    descripcion = models.TextField("descripción")
    estatus = models.CharField(
        "estatus",
        max_length=20,
        choices=Estatus.choices,
        default=Estatus.PENDIENTE,
        db_index=True,
    )
    fecha_fin = models.DateField("fecha fin", null=True, blank=True)
    asignados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="asignados",
        related_name="tarjetas_asignadas",
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
        ]

    def __str__(self):
        return self.titulo
