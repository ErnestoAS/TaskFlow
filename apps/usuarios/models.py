"""
Cuentas de acceso.

Se extiende `AbstractBaseUser` (y no `AbstractUser`) para no arrastrar `username`: la única
credencial es el correo, igual que en mi-campus.

`CodigoCorreo` guarda los códigos de 6 dígitos que se mandan por correo para verificar la cuenta o
recuperar la contraseña (§4.3); las reglas viven en `servicios.py`.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Upper
from django.utils import timezone

from apps.core.models import TimeStampedModel


class UsuarioManager(BaseUserManager):
    """Sin `username`: la cuenta se crea con el correo."""

    use_in_migrations = True

    def get_by_natural_key(self, username):
        return self.get(**{f"{self.model.USERNAME_FIELD}__iexact": username})

    def _crear(self, email, password, **extra):
        if not email:
            raise ValueError("La cuenta necesita un correo.")
        usuario = self.model(email=self.normalize_email(email).lower(), **extra)
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save(using=self._db)
        return usuario

    def create_user(self, email=None, password=None, **extra):
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._crear(email, password, **extra)

    def create_superuser(self, email=None, password=None, **extra):
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        # Lo crea quien administra el servidor: no hay correo que comprobar.
        extra.setdefault("correo_verificado_en", timezone.now())
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Un superusuario necesita is_staff e is_superuser.")
        return self._crear(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField("correo", unique=True)
    nombre = models.CharField("nombre", max_length=100, blank=True)
    primer_apellido = models.CharField("primer apellido", max_length=100, blank=True)
    segundo_apellido = models.CharField("segundo apellido", max_length=100, blank=True)
    correo_verificado_en = models.DateTimeField(
        "correo verificado en",
        null=True,
        blank=True,
        help_text="Vacío: la cuenta aún no confirma su correo y no puede entrar a la app.",
    )
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField(
        "acceso al admin", default=False, help_text="Permite entrar al admin de Django."
    )

    objects = UsuarioManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"
        ordering = ["email"]
        constraints = [
            models.UniqueConstraint(Upper("email"), name="usuario_email_unico_ci"),
        ]

    def __str__(self):
        return self.nombre_completo or self.email

    @property
    def nombre_completo(self) -> str:
        partes = (self.nombre, self.primer_apellido, self.segundo_apellido)
        return " ".join(p for p in partes if p)

    @property
    def correo_verificado(self) -> bool:
        return self.correo_verificado_en is not None

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)


class CodigoCorreo(models.Model):
    """Código de un solo uso enviado por correo. Solo vale el más reciente de cada propósito."""

    class Proposito(models.TextChoices):
        VERIFICAR = "verificar", "Verificar correo"
        RECUPERAR = "recuperar", "Recuperar contraseña"

    usuario = models.ForeignKey(
        Usuario, on_delete=models.CASCADE, related_name="codigos", verbose_name="usuario"
    )
    proposito = models.CharField("propósito", max_length=10, choices=Proposito.choices)
    # HMAC del código, nunca el código en claro: quien lea la base no puede usarlo.
    codigo_hash = models.CharField("código (HMAC)", max_length=64)
    intentos = models.PositiveSmallIntegerField("intentos fallidos", default=0)
    # default y no auto_now_add, para que las pruebas puedan simular un código vencido.
    creado_en = models.DateTimeField("creado en", default=timezone.now)

    class Meta:
        verbose_name = "código por correo"
        verbose_name_plural = "códigos por correo"
        ordering = ["-creado_en"]
        indexes = [models.Index(fields=["usuario", "proposito", "-creado_en"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(proposito__in=["verificar", "recuperar"]),
                name="codigo_correo_proposito_valido",
            ),
        ]

    def __str__(self):
        return f"{self.get_proposito_display()} · {self.usuario}"
