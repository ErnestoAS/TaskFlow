"""Adjuntos de las actividades (Etapa 3.8, §4.4 y §7): subir, descargar, límites y permisos."""

import shutil

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.actividades import servicios as st
from apps.actividades.almacen import comprimir_pdf
from apps.actividades.models import Adjunto
from apps.pizarras import servicios as sp

API = "/api/v1"
KB = 1024
# Un PDF mínimo válido (una página vacía), para probar Ghostscript sin archivos de prueba.
PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)


@pytest.fixture(autouse=True)
def carpeta(settings, tmp_path):
    settings.TASKFLOW_ADJUNTOS_ROOT = tmp_path
    settings.TASKFLOW_ADJUNTO_MAX_MB = 1
    settings.TASKFLOW_ADJUNTOS_PIZARRA_MB = 2
    return tmp_path


@pytest.fixture
def actividad(pizarra, dueno):
    return st.crear_actividad(pizarra, dueno, titulo="Con archivos")


def _archivo(nombre, tamano=10 * KB, contenido=None, tipo="application/octet-stream"):
    return SimpleUploadedFile(nombre, contenido if contenido is not None else b"x" * tamano, tipo)


def _subir(cliente, actividad, archivo):
    return cliente.post(f"{API}/actividades/{actividad.pk}/adjuntos/", {"archivo": archivo})


def test_subir_y_descargar_una_imagen(client, dueno, actividad, carpeta):
    client.force_login(dueno)
    r = _subir(client, actividad, _archivo("foto de la sala.PNG", 20 * KB, tipo="image/png"))
    assert r.status_code == 201, r.json()
    [a] = r.json()["adjuntos"]
    assert (a["nombre"], a["tamano"], a["tipo"]) == ("foto de la sala.PNG", 20 * KB, "image/png")
    assert r.json()["n_adjuntos"] == 1
    guardado = Adjunto.objects.get().archivo.name
    assert guardado.startswith(f"{actividad.pizarra_id}/") and guardado.endswith(".png")
    assert "sala" not in guardado  # el nombre en disco es aleatorio
    assert (carpeta / guardado).exists()
    r = client.get(f"{API}/adjuntos/{a['id']}/")
    assert r.status_code == 200 and r["Content-Type"] == "image/png"
    assert r["Content-Disposition"].startswith("inline")
    assert r["X-Content-Type-Options"] == "nosniff" and r["Content-Security-Policy"] == "sandbox"
    assert b"".join(r.streaming_content) == b"x" * 20 * KB


def test_lo_que_no_es_imagen_ni_pdf_se_descarga(client, dueno, actividad):
    """Un HTML o un SVG no debe poder ejecutarse en el dominio de TaskFlow (§7)."""
    client.force_login(dueno)
    for nombre in ("pagina.html", "dibujo.svg", "datos.xlsx"):
        a = _subir(client, actividad, _archivo(nombre)).json()["adjuntos"][-1]
        r = client.get(f"{API}/adjuntos/{a['id']}/")
        assert r["Content-Type"] == "application/octet-stream"
        assert r["Content-Disposition"].startswith("attachment")


def test_limite_por_archivo_y_por_pizarra(client, dueno, actividad):
    client.force_login(dueno)
    r = _subir(client, actividad, _archivo("grande.bin", 1024 * KB + 1))
    assert r.status_code == 400 and "archivo" in r.json()
    assert _subir(client, actividad, _archivo("a.bin", 900 * KB)).status_code == 201
    assert _subir(client, actividad, _archivo("b.bin", 900 * KB)).status_code == 201
    r = _subir(client, actividad, _archivo("c.bin", 900 * KB))  # pasaría de 2 MB
    assert r.status_code == 400 and "límite" in r.json()["archivo"][0]
    assert Adjunto.objects.count() == 2


def test_quitar_borra_el_archivo_al_confirmar(
    client, dueno, actividad, carpeta, django_capture_on_commit_callbacks
):
    client.force_login(dueno)
    with django_capture_on_commit_callbacks(execute=True):
        a = _subir(client, actividad, _archivo("nota.txt")).json()["adjuntos"][0]
    ruta = carpeta / Adjunto.objects.get().archivo.name
    with django_capture_on_commit_callbacks(execute=True):
        r = client.delete(f"{API}/adjuntos/{a['id']}/")
    assert r.status_code == 200 and r.json()["adjuntos"] == []
    assert not ruta.exists()


def test_eliminar_la_actividad_borra_sus_archivos(
    dueno, actividad, carpeta, django_capture_on_commit_callbacks
):
    with django_capture_on_commit_callbacks(execute=True):
        st.adjuntar(actividad, dueno, _archivo("nota.txt"))
    ruta = carpeta / Adjunto.objects.get().archivo.name
    with django_capture_on_commit_callbacks(execute=True):
        st.eliminar_actividad(actividad, dueno)
    assert not ruta.exists() and not Adjunto.objects.exists()


def test_adjunto_ajeno_es_404_y_sin_permiso_es_403(
    client, dueno, actividad, crear_usuario, agregar_miembro
):
    a = st.adjuntar(actividad, dueno, _archivo("nota.txt"))
    client.force_login(crear_usuario())
    assert _subir(client, actividad, _archivo("x.txt")).status_code == 404
    assert client.get(f"{API}/adjuntos/{a.pk}/").status_code == 404
    assert client.delete(f"{API}/adjuntos/{a.pk}/").status_code == 404
    luis = crear_usuario()
    agregar_miembro(luis, editar=False)
    client.force_login(luis)
    assert _subir(client, actividad, _archivo("x.txt")).status_code == 403
    assert client.delete(f"{API}/adjuntos/{a.pk}/").status_code == 403
    assert client.get(f"{API}/adjuntos/{a.pk}/").status_code == 200  # ver, sí


def test_pizarra_archivada_solo_descarga(client, dueno, actividad, pizarra):
    a = st.adjuntar(actividad, dueno, _archivo("nota.txt"))
    sp.archivar(pizarra, dueno)
    client.force_login(dueno)
    assert _subir(client, actividad, _archivo("x.txt")).status_code == 403
    assert client.get(f"{API}/adjuntos/{a.pk}/").status_code == 200


def test_un_pdf_grande_se_guarda_comprimido_si_sale_mas_chico(
    settings, monkeypatch, dueno, actividad
):
    settings.TASKFLOW_PDF_COMPRIMIR_DESDE_MB = 0
    monkeypatch.setattr(st, "comprimir_pdf", lambda contenido: b"%PDF-1.5 chico")
    a = st.adjuntar(actividad, dueno, _archivo("oficio.pdf", contenido=PDF + b"x" * 5000))
    assert (a.tamano, a.tipo) == (len(b"%PDF-1.5 chico"), "application/pdf")
    # Si comprimido sale más grande (o falla), se queda el original.
    monkeypatch.setattr(st, "comprimir_pdf", lambda contenido: None)
    b = st.adjuntar(actividad, dueno, _archivo("otro.pdf", contenido=PDF))
    assert b.tamano == len(PDF)


@pytest.mark.skipif(not shutil.which("gs"), reason="Sin Ghostscript (va en la imagen de Docker).")
def test_ghostscript_produce_un_pdf():
    salida = comprimir_pdf(PDF)
    assert salida is not None and salida.startswith(b"%PDF-")
    assert comprimir_pdf(b"esto no es un pdf") is None
