from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model

from . import servicios
from .models import Invitacion, MiembroProyecto, Proyecto, TipoTarjeta


class MiembroInline(admin.TabularInline):
    model = MiembroProyecto
    extra = 0
    autocomplete_fields = ["usuario"]
    # El rol no se edita aquí: con la restricción «un solo dueño», intercambiar dos roles en un
    # mismo guardado falla. Para cambiar de dueño se usa «Transferir a» (arriba).
    readonly_fields = ["rol", "unido_en"]
    fields = [
        "usuario",
        "rol",
        "puede_crear",
        "puede_editar",
        "puede_cambiar_estatus",
        "puede_eliminar",
        "puede_gestionar_tipos",
        "unido_en",
    ]


class TipoInline(admin.TabularInline):
    model = TipoTarjeta
    extra = 0
    fields = ["nombre", "color", "descripcion"]


class ProyectoAdminForm(forms.ModelForm):
    transferir_a = forms.ModelChoiceField(
        label="Transferir a",
        queryset=get_user_model().objects.none(),
        required=False,
        help_text="Nuevo dueño (debe ser miembro). El dueño actual queda como miembro con todos "
        "los permisos. Para cuando la cuenta del dueño se desactivó sin transferir (§4.5).",
    )

    class Meta:
        model = Proyecto
        fields = ["nombre", "creado_por", "archivado_en"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["transferir_a"].queryset = get_user_model().objects.filter(
                membresias__proyecto=self.instance, membresias__rol=MiembroProyecto.Rol.MIEMBRO
            )
        else:
            del self.fields["transferir_a"]


@admin.register(Proyecto)
class ProyectoAdmin(admin.ModelAdmin):
    form = ProyectoAdminForm
    list_display = ["nombre", "dueno", "archivado_en", "creado_en"]
    list_filter = [("archivado_en", admin.EmptyFieldListFilter)]
    search_fields = ["nombre", "miembros__usuario__email"]
    autocomplete_fields = ["creado_por"]
    readonly_fields = ["creado_en", "actualizado_en"]
    inlines = [MiembroInline, TipoInline]

    @admin.display(description="dueño")
    def dueno(self, obj):
        return obj.dueno

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        nuevo = form.cleaned_data.get("transferir_a")
        if nuevo:
            servicios.transferir(form.instance, request.user, nuevo, como_administrador=True)
            messages.success(request, f"Proyecto transferido a {nuevo}.")


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ["correo", "proyecto", "estado", "veces_enviada", "enviada_en", "creada_en"]
    list_filter = ["estado"]
    search_fields = ["correo", "proyecto__nombre"]
    readonly_fields = [
        "token",
        "creada_en",
        "enviada_en",
        "veces_enviada",
        "respondida_en",
        "aceptada_por",
    ]
    autocomplete_fields = ["proyecto", "invitada_por"]


@admin.register(TipoTarjeta)
class TipoTarjetaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "proyecto", "color"]
    search_fields = ["nombre", "proyecto__nombre"]
    autocomplete_fields = ["proyecto"]
