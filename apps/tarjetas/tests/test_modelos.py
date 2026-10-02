import pytest

from apps.tarjetas.models import Tarjeta


@pytest.mark.django_db
def test_tarjeta_nace_pendiente_y_admite_varios_asignados(
    proyecto, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    tarjeta = Tarjeta.objects.create(
        proyecto=proyecto, titulo="Revisar informe", descripcion="Primera"
    )
    tarjeta.asignados.add(dueno, luis)

    assert tarjeta.estatus == Tarjeta.Estatus.PENDIENTE
    assert tarjeta.fecha_fin is None
    assert set(tarjeta.asignados.all()) == {dueno, luis}
    assert list(luis.tarjetas_asignadas.all()) == [tarjeta]
