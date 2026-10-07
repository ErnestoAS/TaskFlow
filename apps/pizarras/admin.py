from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model

from . import servicios
from .models import Invitacion, Lista, MiembroPizarra, Pizarra, Solicitante, TipoActividad


class MiembroInline(admin.TabularInline):
    model = MiembroPizarra
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
        "puede_mover",
        "puede_eliminar",
        "puede_gestionar_listas",
        "puede_gestionar_tipos",
        "unido_en",
    ]


class ListaInline(admin.TabularInline):
    model = Lista
    extra = 0
    fields = ["nombre", "posicion"]


class SolicitanteInline(admin.TabularInline):
    model = Solicitante
    extra = 0
    fields = ["nombre"]


class TipoInline(admin.TabularInline):
    model = TipoActividad
    extra = 0
    fields = ["nombre", "color", "descripcion"]


class PizarraAdminForm(forms.ModelForm):
    transferir_a = forms.ModelChoiceField(
        label="Transferir a",
        queryset=get_user_model().objects.none(),
        required=False,
        help_text="Nuevo dueño (debe ser miembro). El dueño actual queda como miembro con todos "
        "los permisos. Para cuando la cuenta del dueño se desactivó sin transferir (§4.5).",
    )

    class Meta:
        model = Pizarra
        fields = ["nombre", "creado_por", "archivada_en"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields["transferir_a"].queryset = get_user_model().objects.filter(
                membresias__pizarra=self.instance, membresias__rol=MiembroPizarra.Rol.MIEMBRO
            )
        else:
            del self.fields["transferir_a"]


@admin.register(Pizarra)
class PizarraAdmin(admin.ModelAdmin):
    form = PizarraAdminForm
    list_display = ["nombre", "dueno", "archivada_en", "creado_en"]
    list_filter = [("archivada_en", admin.EmptyFieldListFilter)]
    search_fields = ["nombre", "miembros__usuario__email"]
    autocomplete_fields = ["creado_por"]
    readonly_fields = ["creado_en", "actualizado_en"]
    inlines = [MiembroInline, ListaInline, TipoInline, SolicitanteInline]

    @admin.display(description="dueño")
    def dueno(self, obj):
        return obj.dueno

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        nuevo = form.cleaned_data.get("transferir_a")
        if nuevo:
            servicios.transferir(form.instance, request.user, nuevo, como_administrador=True)
            messages.success(request, f"Pizarra transferida a {nuevo}.")


@admin.register(Invitacion)
class InvitacionAdmin(admin.ModelAdmin):
    list_display = ["correo", "pizarra", "estado", "veces_enviada", "enviada_en", "creada_en"]
    list_filter = ["estado"]
    search_fields = ["correo", "pizarra__nombre"]
    readonly_fields = [
        "token",
        "creada_en",
        "enviada_en",
        "veces_enviada",
        "respondida_en",
        "aceptada_por",
    ]
    autocomplete_fields = ["pizarra", "invitada_por"]


@admin.register(Lista)
class ListaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "pizarra", "posicion"]
    search_fields = ["nombre", "pizarra__nombre"]
    autocomplete_fields = ["pizarra"]


@admin.register(TipoActividad)
class TipoActividadAdmin(admin.ModelAdmin):
    list_display = ["nombre", "pizarra", "color"]
    search_fields = ["nombre", "pizarra__nombre"]
    autocomplete_fields = ["pizarra"]
