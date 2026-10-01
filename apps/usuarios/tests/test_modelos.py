import pytest
from django.contrib.auth import get_user_model


@pytest.mark.django_db
def test_correo_se_guarda_en_minusculas():
    usuario = get_user_model().objects.create_user("Ana@Ejemplo.COM", "x")
    assert usuario.email == "ana@ejemplo.com"


@pytest.mark.django_db
def test_superusuario():
    usuario = get_user_model().objects.create_superuser("admin@ejemplo.com", "x")
    assert usuario.is_staff and usuario.is_superuser
