import pytest
from django.utils import timezone

from apps.tarjetas.models import Tarjeta


@pytest.mark.django_db
def test_tarjeta_por_omision_y_varios_asignados(
    pizarra, listas, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    tarjeta = Tarjeta.objects.create(
        pizarra=pizarra, lista=listas["Pendiente"], titulo="Revisar informe"
    )
    tarjeta.asignados.add(dueno, luis)

    assert tarjeta.descripcion == "" and tarjeta.prioridad == "media"
    assert tarjeta.fecha_inicio == timezone.localdate() and tarjeta.fecha_fin is None
    assert set(tarjeta.asignados.all()) == {dueno, luis}
    assert list(luis.tarjetas_asignadas.all()) == [tarjeta]
