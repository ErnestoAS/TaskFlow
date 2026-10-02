import pytest

from apps.proyectos.models import MiembroProyecto
from apps.tarjetas.models import Tarjeta
from apps.tarjetas.servicios import crear_tarjeta

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(crear_usuario, client):
    usuario = crear_usuario("admin@ejemplo.mx", is_staff=True, is_superuser=True)
    client.force_login(usuario)
    return usuario


def test_cambiar_estatus_en_el_admin_deja_rastro(admin, client, proyecto, dueno):
    t = crear_tarjeta(proyecto, dueno, titulo="Una", descripcion="x")
    datos = {
        "proyecto": proyecto.pk,
        "titulo": "Una",
        "descripcion": "x",
        "estatus": "finalizada",
        "prioridad": "media",
        "fecha_fin": "",
        "creada_por": dueno.pk,
        "cambios_estatus-TOTAL_FORMS": "1",
        "cambios_estatus-INITIAL_FORMS": "1",
        "cambios_estatus-MIN_NUM_FORMS": "0",
        "cambios_estatus-MAX_NUM_FORMS": "1000",
        "cambios_estatus-0-id": t.cambios_estatus.get().pk,
        "cambios_estatus-0-tarjeta": t.pk,
    }
    r = client.post(f"/django-admin/tarjetas/tarjeta/{t.pk}/change/", datos)
    assert r.status_code == 302, r.content.decode()[:2000]
    t = Tarjeta.objects.get(pk=t.pk)
    assert t.estatus == "finalizada"
    ultimo = t.cambios_estatus.first()
    assert (ultimo.estatus_anterior, ultimo.estatus_nuevo, ultimo.usuario) == (
        "pendiente",
        "finalizada",
        admin,
    )


def test_el_admin_transfiere_un_proyecto(
    admin, client, proyecto, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    m_luis = agregar_miembro(luis)
    m_dueno = MiembroProyecto.objects.get(proyecto=proyecto, usuario=dueno)
    filas = {}
    for i, m in enumerate([m_dueno, m_luis]):
        filas.update(
            {
                f"miembros-{i}-id": m.pk,
                f"miembros-{i}-proyecto": proyecto.pk,
                f"miembros-{i}-usuario": m.usuario.pk,
                f"miembros-{i}-puede_crear": "on",
                f"miembros-{i}-puede_editar": "on",
                f"miembros-{i}-puede_cambiar_estatus": "on",
            }
        )
    datos = {
        "nombre": proyecto.nombre,
        "creado_por": dueno.pk,
        "archivado_en_0": "",
        "archivado_en_1": "",
        "transferir_a": luis.pk,
        "miembros-TOTAL_FORMS": "2",
        "miembros-INITIAL_FORMS": "2",
        "miembros-MIN_NUM_FORMS": "0",
        "miembros-MAX_NUM_FORMS": "1000",
        "tipos-TOTAL_FORMS": "0",
        "tipos-INITIAL_FORMS": "0",
        "tipos-MIN_NUM_FORMS": "0",
        "tipos-MAX_NUM_FORMS": "1000",
        **filas,
    }
    r = client.post(f"/django-admin/proyectos/proyecto/{proyecto.pk}/change/", datos)
    assert r.status_code == 302, r.content.decode()[:3000]
    assert proyecto.dueno == luis
