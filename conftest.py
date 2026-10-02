"""Fixtures compartidas por las pruebas de todas las apps."""

import itertools

import pytest

_n = itertools.count(1)


@pytest.fixture(autouse=True)
def _cache_limpia():
    """Los límites de intentos (DRF) se cuentan en la caché: cada prueba empieza en cero."""
    from django.core.cache import cache

    cache.clear()


@pytest.fixture
def crear_usuario(db):
    from django.contrib.auth import get_user_model
    from django.utils import timezone

    def _crear(correo=None, **extra):
        """Cuenta con el correo ya verificado; `correo_verificado_en=None` para una pendiente."""
        correo = correo or f"persona{next(_n)}@ejemplo.mx"
        extra.setdefault("correo_verificado_en", timezone.now())
        return get_user_model().objects.create_user(correo, "contraseña-de-prueba", **extra)

    return _crear


@pytest.fixture
def dueno(crear_usuario):
    return crear_usuario("dueno@ejemplo.mx")


@pytest.fixture
def proyecto(dueno):
    from apps.proyectos.servicios import crear_proyecto

    return crear_proyecto(dueno, "Semana de la Ciencia")


@pytest.fixture
def agregar_miembro(proyecto):
    """Agrega un miembro con los permisos por omisión (los de quien acepta una invitación)."""
    from apps.proyectos.models import MiembroProyecto

    def _agregar(usuario, p=None, **permisos):
        return MiembroProyecto.objects.create(
            proyecto=p or proyecto,
            usuario=usuario,
            **{f"puede_{k}": v for k, v in permisos.items()},
        )

    return _agregar
