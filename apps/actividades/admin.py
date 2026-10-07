from django.contrib import admin

from .models import Actividad, ElementoChecklist, Movimiento
from .servicios import registrar_movimiento


class MovimientoInline(admin.TabularInline):
    model = Movimiento
    extra = 0
    can_delete = False
    fields = ["fecha", "usuario", "lista_anterior", "lista_nueva", "nota"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ElementoChecklistInline(admin.TabularInline):
    model = ElementoChecklist
    fk_name = "actividad"
    extra = 0
    fields = ["texto", "hecho", "posicion", "actividad_creada"]
    raw_id_fields = ["actividad_creada"]


@admin.register(Actividad)
class ActividadAdmin(admin.ModelAdmin):
    list_display = [
        "titulo",
        "pizarra",
        "lista",
        "fecha_solicitud",
        "fecha_fin",
        "creada_por",
        "creado_en",
    ]
    list_filter = ["pizarra"]
    search_fields = ["titulo", "descripcion", "pizarra__nombre", "lista__nombre"]
    autocomplete_fields = [
        "pizarra",
        "lista",
        "lista_terminado",
        "lista_al_completar",
        "asignados",
        "tipos",
        "solicitada_por",
        "creada_por",
    ]
    readonly_fields = ["creado_en", "actualizado_en"]
    inlines = [ElementoChecklistInline, MovimientoInline]

    def save_model(self, request, obj, form, change):
        # El admin también deja rastro en el historial (§4.6): ningún cambio de lista sin fila.
        anterior = Actividad.objects.get(pk=obj.pk).lista.nombre if change else ""
        super().save_model(request, obj, form, change)
        if not change or "lista" in form.changed_data:
            registrar_movimiento(obj, request.user, anterior, obj.lista.nombre)
