import pytest

from apps.actividades.models import Actividad


@pytest.mark.django_db
def test_actividad_por_omision_y_varios_asignados(
    pizarra, listas, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    agregar_miembro(luis)
    actividad = Actividad.objects.create(
        pizarra=pizarra, lista=listas["Pendiente"], titulo="Revisar informe"
    )
    actividad.asignados.add(dueno, luis)

    assert actividad.descripcion == ""
    assert actividad.fecha_solicitud is None and actividad.fecha_fin is None
    assert set(actividad.asignados.all()) == {dueno, luis}
    assert list(luis.actividades_asignadas.all()) == [actividad]
