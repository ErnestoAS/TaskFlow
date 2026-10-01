"""
Cuentas de acceso.

Se extiende `AbstractBaseUser` (y no `AbstractUser`) para no arrastrar `username`: la única
credencial es el correo, igual que en mi-campus.
"""

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.functions import Upper

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
        if not extra["is_staff"] or not extra["is_superuser"]:
            raise ValueError("Un superusuario necesita is_staff e is_superuser.")
        return self._crear(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    email = models.EmailField("correo", unique=True)
    nombre = models.CharField("nombre", max_length=100, blank=True)
    apellidos = models.CharField("apellidos", max_length=150, blank=True)
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
        return f"{self.nombre} {self.apellidos}".strip()

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)
