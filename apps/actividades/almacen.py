"""
Dónde y cómo se guardan los adjuntos (Etapa 3.8, §4.4 y §7 de la propuesta).

- Fuera de `MEDIA_URL`: `AlmacenAdjuntos` no tiene URL pública (`url()` falla a propósito); se
  descargan solo por la API, que revisa que el usuario sea miembro de la pizarra.
- Nombre aleatorio en disco (`<pizarra>/<uuid4><ext>`): el original puede traer caracteres raros o
  repetirse, y no debe poder adivinarse. El original se guarda en `Adjunto.nombre`.
- Los PDF grandes se comprimen con Ghostscript; las imágenes ya llegan reducidas desde la PWA.
"""

import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible

# Se muestran en el navegador; todo lo demás (también SVG y HTML) se descarga (§7).
TIPOS_EN_LINEA = {"image/jpeg", "image/png", "image/webp", "image/gif", "application/pdf"}


@deconstructible
class AlmacenAdjuntos(FileSystemStorage):
    """`TASKFLOW_ADJUNTOS_ROOT` leído en cada uso (las pruebas lo cambian), sin URL pública."""

    def __init__(self):
        super().__init__()

    @property
    def base_location(self):
        return settings.TASKFLOW_ADJUNTOS_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)

    @property
    def base_url(self):
        return None

    def url(self, name):
        raise ValueError("Los adjuntos no tienen URL pública: se descargan por la API.")


def ruta_adjunto(instancia, nombre: str) -> str:
    extension = Path(nombre).suffix.lower()
    if not re.fullmatch(r"\.[a-z0-9]{1,8}", extension):
        extension = ""
    return f"{instancia.actividad.pizarra_id}/{uuid.uuid4().hex}{extension}"


def comprimir_pdf(contenido: bytes) -> bytes | None:
    """
    Versión comprimida del PDF con Ghostscript (`/ebook`: imágenes a 150 ppp), o None si no se pudo
    (sin Ghostscript, PDF dañado, tardó demasiado). Quien llama decide si conviene.
    """
    gs = shutil.which("gs")
    if not gs:
        return None
    with tempfile.TemporaryDirectory() as carpeta:
        entrada, salida = Path(carpeta, "entrada.pdf"), Path(carpeta, "salida.pdf")
        entrada.write_bytes(contenido)
        try:
            subprocess.run(
                [
                    gs,
                    "-sDEVICE=pdfwrite",
                    "-dCompatibilityLevel=1.5",
                    "-dPDFSETTINGS=/ebook",
                    "-dSAFER",
                    "-dNOPAUSE",
                    "-dQUIET",
                    "-dBATCH",
                    f"-sOutputFile={salida}",
                    str(entrada),
                ],
                check=True,
                timeout=60,
                capture_output=True,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        return salida.read_bytes() if salida.exists() else None
