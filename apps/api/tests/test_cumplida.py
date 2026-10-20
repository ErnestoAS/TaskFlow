"""«Cumplida» (2026-10-20, §4.4–§6): marcar, desmarcar, deja de estar vencida y permisos."""

import datetime

from django.utils import timezone

from apps.actividades import servicios as st
from apps.actividades.models import Movimiento
from apps.pizarras import servicios as sp

API = "/api/v1"


def _cumplida(client, actividad, valor):
    return client.post(
        f"{API}/actividades/{actividad.pk}/cumplida/",
        {"cumplida": valor},
        content_type="application/json",
    )


def _vencida(pizarra, dueno):
    ayer = timezone.localdate() - datetime.timedelta(days=1)
    return st.crear_actividad(pizarra, dueno, titulo="Entregar informe", fecha_fin=ayer)


def test_marcar_y_desmarcar_queda_en_el_historial(client, dueno, pizarra):
    t = _vencida(pizarra, dueno)
    client.force_login(dueno)
    r = _cumplida(client, t, True)
    assert r.status_code == 200
    assert r.json()["cumplida_en"] and r.json()["cumplida_por"]["id"] == dueno.pk
    assert r.json()["historial"][0]["nota"] == "la marcó como cumplida"
    _cumplida(client, t, True)  # otra vez: no cambia nada ni deja otra fila
    r = _cumplida(client, t, False)
    assert r.json()["cumplida_en"] is None and r.json()["cumplida_por"] is None
    notas = list(
        Movimiento.objects.filter(actividad=t).exclude(nota="").values_list("nota", flat=True)
    )
    assert sorted(notas) == ["la marcó como cumplida", "la volvió a abrir"]


def test_la_cumplida_no_cuenta_como_vencida(client, dueno, pizarra):
    t = _vencida(pizarra, dueno)
    client.force_login(dueno)

    def vencidas():
        [p] = client.get(f"{API}/pizarras/").json()
        return p["conteos"]["vencidas"]

    assert vencidas() == 1
    st.marcar_cumplida(t, dueno, True)
    assert vencidas() == 0


def test_solo_con_fecha_de_vencimiento_y_quitarla_la_desmarca(client, dueno, pizarra):
    sin_fecha = st.crear_actividad(pizarra, dueno, titulo="Sin fecha")
    client.force_login(dueno)
    r = _cumplida(client, sin_fecha, True)
    assert r.status_code == 400 and "cumplida" in r.json()
    t = _vencida(pizarra, dueno)
    st.marcar_cumplida(t, dueno, True)
    st.editar_actividad(t, dueno, fecha_fin=None)
    t.refresh_from_db()
    assert t.cumplida_en is None and t.cumplida_por is None


def test_ajena_es_404_sin_editar_es_403_y_archivada_tambien(
    client, dueno, pizarra, crear_usuario, agregar_miembro
):
    t = _vencida(pizarra, dueno)
    client.force_login(crear_usuario())
    assert _cumplida(client, t, True).status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, editar=False)
    client.force_login(luis)
    assert _cumplida(client, t, True).status_code == 403
    sp.archivar(pizarra, dueno)
    client.force_login(dueno)
    assert _cumplida(client, t, True).status_code == 403
