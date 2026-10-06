"""
Tarjetas: la unidad de trabajo de TaskFlow (§4.4 y §4.6 de la propuesta).

Cada tarjeta pertenece a una pizarra y está en una de sus listas, en una posición (orden manual).
Tiene título, descripción opcional, prioridad, fecha de inicio, fecha límite opcional, cero o más
asignados (miembros de la pizarra), cero o más tipos (de la misma pizarra) y una checklist. Cada
creación, movimiento entre listas y conversión de la checklist queda en `Movimiento`.

Las reglas (permisos, que los asignados sean miembros, que lista y tipos sean de la pizarra)
viven en `servicios.py`: la base de datos no puede expresarlas.
"""

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.core.models import TimeStampedModel


class Prioridad(models.TextChoices):
    """Fija para todas las pizarras (decidido 2026-10-01), a diferencia de los tipos."""

    BAJA = "baja", "Baja"
    MEDIA = "media", "Media"
    ALTA = "alta", "Alta"
    URGENTE = "urgente", "Urgente"


# Para ordenar de más a menos urgente sin depender del orden alfabético.
ORDEN_PRIORIDAD = {"urgente": 0, "alta": 1, "media": 2, "baja": 3}


def hoy():
    """Fecha de hoy en la zona de TaskFlow (America/Mexico_City), no en UTC."""
    return timezone.localdate()


class Tarjeta(TimeStampedModel):
    Prioridad = Prioridad

    pizarra = models.ForeignKey(
        "pizarras.Pizarra",
        verbose_name="pizarra",
        on_delete=models.CASCADE,
        related_name="tarjetas",
    )
    # RESTRICT: una lista con tarjetas no se borra sola (§4.6), pero sí junto con su pizarra
    # (PROTECT lo impediría también ahí).
    lista = models.ForeignKey(
        "pizarras.Lista",
        verbose_name="lista",
        on_delete=models.RESTRICT,
        related_name="tarjetas",
    )
    posicion = models.PositiveIntegerField("posición", default=0)
    titulo = models.CharField("título", max_length=200)
    # Opcional (2026-10-05): muchas actividades se explican con el título.
    descripcion = models.TextField("descripción", blank=True)
    prioridad = models.CharField(
        "prioridad", max_length=10, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    # Cuándo empezó o se encargó, que no siempre es cuándo se capturó (creado_en).
    fecha_inicio = models.DateField("fecha de inicio", default=hoy)
    fecha_fin = models.DateField("fecha límite", null=True, blank=True)
    asignados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="asignados",
        related_name="tarjetas_asignadas",
        blank=True,
    )
    tipos = models.ManyToManyField(
        "pizarras.TipoTarjeta",
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
    # Para las tarjetas que nacieron de su checklist (2026-10-06): cuando una llega a esta lista,
    # su elemento se palomea solo. Una por tarjeta, no por elemento ni por lista de la pizarra:
    # «terminado» depende de lo que se esté siguiendo, no es una propiedad de la lista.
    lista_terminado = models.ForeignKey(
        "pizarras.Lista",
        verbose_name="lo que llega a esta lista cuenta como terminado",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Vacía: los elementos de la checklist se palomean a mano.",
    )

    class Meta:
        verbose_name = "tarjeta"
        verbose_name_plural = "tarjetas"
        ordering = ["posicion", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(prioridad__in=["baja", "media", "alta", "urgente"]),
                name="tarjeta_prioridad_valida",
            ),
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=F("fecha_inicio")),
                name="tarjeta_fechas_en_orden",
            ),
        ]
        indexes = [models.Index(fields=["lista", "posicion"], name="tarjeta_lista_posicion")]

    def __str__(self):
        return self.titulo


class Movimiento(models.Model):
    """
    Historial de la tarjeta (§4.6): quién la creó o la movió de qué lista a cuál, fecha y hora.
    Guarda el NOMBRE de las listas (no una FK) porque las listas se renombran y se eliminan, y el
    historial debe seguir diciendo lo que pasó. `lista_anterior` vacía = la creación. `nota`
    describe un evento que no es un movimiento (convertir un elemento de la checklist).

    Solo se agregan filas; las escriben los servicios en la misma transacción que el cambio.
    """

    tarjeta = models.ForeignKey(
        Tarjeta, verbose_name="tarjeta", on_delete=models.CASCADE, related_name="movimientos"
    )
    lista_anterior = models.CharField("lista anterior", max_length=50, blank=True)
    lista_nueva = models.CharField("lista nueva", max_length=50, blank=True)
    nota = models.CharField("nota", max_length=300, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="usuario",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movimientos",
        help_text="Vacío si la cuenta se borró: el movimiento se conserva («Usuario eliminado»).",
    )
    fecha = models.DateTimeField("fecha", default=timezone.now)

    class Meta:
        verbose_name = "movimiento"
        verbose_name_plural = "historial"
        ordering = ["-fecha", "-id"]
        indexes = [models.Index(fields=["tarjeta", "-fecha"], name="movimiento_tarjeta_fecha")]

    def __str__(self):
        if self.nota:
            return f"{self.tarjeta}: {self.nota}"
        de = self.lista_anterior or "creación"
        return f"{self.tarjeta}: {de} → {self.lista_nueva}"


class ElementoChecklist(TimeStampedModel):
    """
    Un renglón de la checklist de una tarjeta (§4.6). Se puede convertir en una tarjeta enlazada
    (`tarjeta_creada`); entonces, si la tarjeta de la checklist tiene `lista_terminado`, el
    elemento está hecho cuando su tarjeta está en esa lista. Si no, se palomea a mano.
    """

    tarjeta = models.ForeignKey(
        Tarjeta, verbose_name="tarjeta", on_delete=models.CASCADE, related_name="checklist"
    )
    texto = models.CharField("texto", max_length=200)
    hecho = models.BooleanField("hecho", default=False)
    posicion = models.PositiveIntegerField("posición", default=0)
    # El enlace vive solo aquí; la tarjeta nueva lo lee con `elemento_origen` (relación inversa).
    tarjeta_creada = models.OneToOneField(
        Tarjeta,
        verbose_name="tarjeta creada",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="elemento_origen",
    )

    class Meta:
        verbose_name = "elemento de checklist"
        verbose_name_plural = "checklist"
        ordering = ["posicion", "id"]

    def __str__(self):
        return self.texto

    @property
    def automatico(self) -> bool:
        """Se palomea solo: convertido en tarjeta y con lista elegida en su tarjeta."""
        return bool(self.tarjeta_creada_id and self.tarjeta.lista_terminado_id)

    @property
    def esta_hecho(self) -> bool:
        if self.automatico:
            return self.tarjeta_creada.lista_id == self.tarjeta.lista_terminado_id
        return self.hecho
