from django.contrib import admin

from .models import Tarjeta


@admin.register(Tarjeta)
class TarjetaAdmin(admin.ModelAdmin):
    list_display = ["titulo", "estatus", "fecha_fin", "creada_por", "creado_en"]
    list_filter = ["estatus"]
    search_fields = ["titulo", "descripcion"]
    autocomplete_fields = ["asignados", "creada_por"]
    readonly_fields = ["creado_en", "actualizado_en"]
