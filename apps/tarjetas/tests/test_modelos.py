import pytest
from django.contrib.auth import get_user_model

from apps.tarjetas.models import Tarjeta


@pytest.mark.django_db
def test_tarjeta_nace_pendiente_y_admite_varios_asignados():
    Usuario = get_user_model()
    ana = Usuario.objects.create_user("ana@ejemplo.com", "x")
    luis = Usuario.objects.create_user("luis@ejemplo.com", "x")

    tarjeta = Tarjeta.objects.create(titulo="Revisar informe", descripcion="Primera revisión")
    tarjeta.asignados.add(ana, luis)

    assert tarjeta.estatus == Tarjeta.Estatus.PENDIENTE
    assert tarjeta.fecha_fin is None
    assert set(tarjeta.asignados.all()) == {ana, luis}
    assert list(ana.tarjetas_asignadas.all()) == [tarjeta]
