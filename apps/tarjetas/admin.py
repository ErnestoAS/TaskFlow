from django.contrib import admin

from .models import CambioEstatus, Tarjeta
from .servicios import registrar_cambio


class CambioEstatusInline(admin.TabularInline):
    model = CambioEstatus
    extra = 0
    can_delete = False
    fields = ["fecha", "usuario", "estatus_anterior", "estatus_nuevo"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = [
        "titulo",
        "proyecto",
        "estatus",
        "prioridad",
        "fecha_fin",
        "creada_por",
        "creado_en",
    ]
    list_filter = ["estatus", "prioridad", "proyecto"]
    search_fields = ["titulo", "descripcion", "proyecto__nombre"]
    autocomplete_fields = ["proyecto", "asignados", "tipos", "creada_por"]
    readonly_fields = ["creado_en", "actualizado_en"]
    inlines = [CambioEstatusInline]

    def save_model(self, request, obj, form, change):
        # El admin también deja rastro en el historial (§4.5): ningún cambio de estatus sin fila.
        anterior = form.initial.get("estatus", "") if change else ""
        super().save_model(request, obj, form, change)
        if not change or "estatus" in form.changed_data:
            registrar_cambio(obj, request.user, anterior, obj.estatus)
