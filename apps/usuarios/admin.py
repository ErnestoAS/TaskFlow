from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.utils import timezone

from .models import Usuario


class UsuarioCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = Usuario
        fields = ("email",)


class UsuarioChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = Usuario
        fields = "__all__"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    form = UsuarioChangeForm
    add_form = UsuarioCreationForm
    list_display = ["email", "nombre_completo", "correo_verificado_en", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "is_superuser"]
    search_fields = ["email", "nombre", "primer_apellido", "segundo_apellido"]
    ordering = ["email"]
    readonly_fields = ["last_login", "creado_en", "actualizado_en"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("nombre", "primer_apellido", "segundo_apellido")}),
        (
            "Permisos",
            {
                "fields": (
                    "is_active",
                    "correo_verificado_en",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Fechas", {"fields": ("last_login", "creado_en", "actualizado_en")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)

    def save_model(self, request, obj, form, change):
        # Una cuenta creada desde el admin la da de alta alguien de confianza: no pide código.
        if not change and obj.correo_verificado_en is None:
            obj.correo_verificado_en = timezone.now()
        super().save_model(request, obj, form, change)
