"""
Actividades: la unidad de trabajo de TaskFlow (§4.4 y §4.6 de la propuesta).

Cada actividad pertenece a una pizarra y está en una de sus listas, en una posición (orden manual).
Tiene título, descripción, fecha de solicitud y fecha límite (opcionales), cero o más
asignados (miembros de la pizarra), cero o más tipos (de la misma pizarra) y una checklist. Cada
creación, movimiento entre listas y conversión de la checklist queda en `Movimiento`.

Las reglas (permisos, que los asignados sean miembros, que lista y tipos sean de la pizarra)
viven en `servicios.py`: la base de datos no puede expresarlas.
"""

from django.conf import settings
from django.db import models, transaction
from django.db.models import F, Q
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import timezone

from apps.core.models import TimeStampedModel

from .almacen import AlmacenAdjuntos, ruta_adjunto


def hoy():
    """Fecha de hoy en la zona de TaskFlow (America/Mexico_City), no en UTC."""
    return timezone.localdate()


class Actividad(TimeStampedModel):
    pizarra = models.ForeignKey(
        "pizarras.Pizarra",
        verbose_name="pizarra",
        on_delete=models.CASCADE,
        related_name="actividades",
    )
    # RESTRICT: una lista con actividades no se borra sola (§4.6), pero sí junto con su pizarra
    # (PROTECT lo impediría también ahí).
    lista = models.ForeignKey(
        "pizarras.Lista",
        verbose_name="lista",
        on_delete=models.RESTRICT,
        related_name="actividades",
    )
    posicion = models.PositiveIntegerField("posición", default=0)
    titulo = models.CharField("título", max_length=200)
    # Opcional (2026-10-05): muchas actividades se explican con el título.
    descripcion = models.TextField("descripción", blank=True)
    # Cuándo se solicitó, que no siempre es cuándo se capturó (creado_en). Opcional y sin valor por
    # omisión desde la Etapa 3.8 (antes `fecha_inicio`, con hoy): con hoy repetía `creado_en`.
    fecha_solicitud = models.DateField("solicitada el", null=True, blank=True)
    fecha_fin = models.DateField("vence el", null=True, blank=True)
    asignados = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name="asignados",
        related_name="actividades_asignadas",
        blank=True,
    )
    tipos = models.ManyToManyField(
        "pizarras.TipoActividad",
        verbose_name="tipos",
        related_name="actividades",
        blank=True,
    )
    # Quién la solicitó (Etapa 3.8, §4.4): un miembro o un externo del catálogo de la pizarra, a
    # lo más uno. Dos FK y no una: los miembros ya son usuarios y copiarlos al catálogo los
    # dejaría desactualizados (§9).
    solicitada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="solicitada por (miembro)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actividades_solicitadas",
    )
    solicitante_externo = models.ForeignKey(
        "pizarras.Solicitante",
        verbose_name="solicitada por (externo)",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actividades",
    )
    creada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="creada por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="actividades_creadas",
    )
    # Para las actividades que nacieron de su checklist (2026-10-06): cuando una llega a esta lista,
    # su elemento se palomea solo. Una por actividad, no por elemento ni por lista de la pizarra:
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
    # «Mover a [lista] al completar» (Etapa 3.8): cuando su checklist pasa de incompleta a
    # completa, la actividad se mueve sola al final de esta lista. Despalomear no la regresa.
    lista_al_completar = models.ForeignKey(
        "pizarras.Lista",
        verbose_name="al completar la checklist, mover a",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Vacía: completar la checklist no la mueve.",
    )

    class Meta:
        verbose_name = "actividad"
        verbose_name_plural = "actividades"
        ordering = ["posicion", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(fecha_fin__isnull=True)
                | Q(fecha_solicitud__isnull=True)
                | Q(fecha_fin__gte=F("fecha_solicitud")),
                name="actividad_fechas_en_orden",
            ),
            models.CheckConstraint(
                condition=Q(solicitada_por__isnull=True) | Q(solicitante_externo__isnull=True),
                name="actividad_un_solicitante",
            ),
        ]
        indexes = [models.Index(fields=["lista", "posicion"], name="actividad_lista_posicion")]

    def __str__(self):
        return self.titulo


class Movimiento(models.Model):
    """
    Historial de la actividad (§4.6): quién la creó o la movió de qué lista a cuál, fecha y hora.
    Guarda el NOMBRE de las listas (no una FK) porque las listas se renombran y se eliminan, y el
    historial debe seguir diciendo lo que pasó. `lista_anterior` vacía = la creación. `nota`
    describe un evento que no es un movimiento (convertir un elemento de la checklist).

    Solo se agregan filas; las escriben los servicios en la misma transacción que el cambio.
    """

    actividad = models.ForeignKey(
        Actividad, verbose_name="actividad", on_delete=models.CASCADE, related_name="movimientos"
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
        indexes = [models.Index(fields=["actividad", "-fecha"], name="movimiento_actividad_fecha")]

    def __str__(self):
        if self.nota:
            return f"{self.actividad}: {self.nota}"
        de = self.lista_anterior or "creación"
        return f"{self.actividad}: {de} → {self.lista_nueva}"


class ElementoChecklist(TimeStampedModel):
    """
    Un renglón de la checklist de una actividad (§4.6). Se puede convertir en una actividad enlazada
    (`actividad_creada`); entonces, si la actividad de la checklist tiene `lista_terminado`, el
    elemento está hecho cuando su actividad está en esa lista. Si no, se palomea a mano.
    """

    actividad = models.ForeignKey(
        Actividad, verbose_name="actividad", on_delete=models.CASCADE, related_name="checklist"
    )
    # 400 desde la Etapa 3.8 (antes 200): hay pasos que necesitan una explicación.
    texto = models.CharField("texto", max_length=400)
    hecho = models.BooleanField("hecho", default=False)
    posicion = models.PositiveIntegerField("posición", default=0)
    # El enlace vive solo aquí; la actividad nueva lo lee con `elemento_origen` (relación inversa).
    actividad_creada = models.OneToOneField(
        Actividad,
        verbose_name="actividad creada",
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
        """Se palomea solo: convertido en actividad y con lista elegida en su actividad."""
        return bool(self.actividad_creada_id and self.actividad.lista_terminado_id)

    @property
    def esta_hecho(self) -> bool:
        if self.automatico:
            return self.actividad_creada.lista_id == self.actividad.lista_terminado_id
        return self.hecho


class Adjunto(TimeStampedModel):
    """
    Archivo de una actividad (Etapa 3.8, §4.4). Límites, compresión y permisos en `servicios.py`;
    dónde se guarda y cómo se entrega, en `almacen.py` y §7.
    """

    actividad = models.ForeignKey(
        Actividad, verbose_name="actividad", on_delete=models.CASCADE, related_name="adjuntos"
    )
    archivo = models.FileField(
        "archivo", upload_to=ruta_adjunto, storage=AlmacenAdjuntos(), max_length=200
    )
    nombre = models.CharField("nombre", max_length=255)
    tamano = models.PositiveBigIntegerField("tamaño (bytes)")
    tipo = models.CharField("tipo", max_length=100)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="subido por",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="adjuntos",
    )

    class Meta:
        verbose_name = "adjunto"
        verbose_name_plural = "adjuntos"
        ordering = ["creado_en", "id"]

    def __str__(self):
        return self.nombre


@receiver(post_delete, sender=Adjunto)
def _borrar_archivo(sender, instance: Adjunto, **kwargs):
    """También al borrar su actividad o su pizarra (CASCADE). Después del commit: si la
    transacción se revierte, el archivo sigue ahí."""
    nombre, almacen = instance.archivo.name, instance.archivo.storage
    if nombre:
        transaction.on_commit(lambda: almacen.delete(nombre))
