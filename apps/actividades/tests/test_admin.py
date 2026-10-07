import pytest

from apps.actividades.models import Actividad
from apps.actividades.servicios import crear_actividad
from apps.pizarras.models import MiembroPizarra

pytestmark = pytest.mark.django_db

VACIO = {"TOTAL_FORMS": "0", "INITIAL_FORMS": "0", "MIN_NUM_FORMS": "0", "MAX_NUM_FORMS": "1000"}


def _formset(prefijo, total=0, iniciales=0):
    return {
        f"{prefijo}-{k}": v
        for k, v in {**VACIO, "TOTAL_FORMS": str(total), "INITIAL_FORMS": str(iniciales)}.items()
    }


@pytest.fixture
def admin(crear_usuario, client):
    usuario = crear_usuario("admin@ejemplo.mx", is_staff=True, is_superuser=True)
    client.force_login(usuario)
    return usuario


def test_mover_de_lista_en_el_admin_deja_rastro(admin, client, pizarra, dueno, listas):
    t = crear_actividad(pizarra, dueno, titulo="Una")
    datos = {
        "pizarra": pizarra.pk,
        "lista": listas["Finalizada"].pk,
        "posicion": 0,
        "titulo": "Una",
        "descripcion": "",
        "fecha_solicitud": "",
        "fecha_fin": "",
        "creada_por": dueno.pk,
        **_formset("checklist"),
        **_formset("movimientos", 1, 1),
        "movimientos-0-id": t.movimientos.get().pk,
        "movimientos-0-actividad": t.pk,
    }
    r = client.post(f"/django-admin/actividades/actividad/{t.pk}/change/", datos)
    assert r.status_code == 302, r.content.decode()[:2000]
    t = Actividad.objects.get(pk=t.pk)
    assert t.lista == listas["Finalizada"]
    ultimo = t.movimientos.first()
    assert (ultimo.lista_anterior, ultimo.lista_nueva, ultimo.usuario) == (
        "Pendiente",
        "Finalizada",
        admin,
    )


def test_el_admin_transfiere_una_pizarra(
    admin, client, pizarra, dueno, crear_usuario, agregar_miembro
):
    luis = crear_usuario()
    m_luis = agregar_miembro(luis)
    m_dueno = MiembroPizarra.objects.get(pizarra=pizarra, usuario=dueno)
    filas = {}
    for i, m in enumerate([m_dueno, m_luis]):
        filas.update(
            {
                f"miembros-{i}-id": m.pk,
                f"miembros-{i}-pizarra": pizarra.pk,
                f"miembros-{i}-usuario": m.usuario.pk,
                f"miembros-{i}-puede_crear": "on",
                f"miembros-{i}-puede_editar": "on",
                f"miembros-{i}-puede_mover": "on",
            }
        )
    listas = list(pizarra.listas.all())
    for i, lista in enumerate(listas):
        filas.update(
            {
                f"listas-{i}-id": lista.pk,
                f"listas-{i}-pizarra": pizarra.pk,
                f"listas-{i}-nombre": lista.nombre,
                f"listas-{i}-posicion": lista.posicion,
            }
        )
    datos = {
        "nombre": pizarra.nombre,
        "creado_por": dueno.pk,
        "archivada_en_0": "",
        "archivada_en_1": "",
        "transferir_a": luis.pk,
        **_formset("miembros", 2, 2),
        **_formset("listas", len(listas), len(listas)),
        **_formset("tipos"),
        **_formset("solicitantes"),
        **filas,
    }
    r = client.post(f"/django-admin/pizarras/pizarra/{pizarra.pk}/change/", datos)
    assert r.status_code == 302, r.content.decode()[:3000]
    assert pizarra.dueno == luis
