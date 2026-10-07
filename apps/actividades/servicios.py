"""
Reglas de negocio de las actividades y su checklist (§4.6 de la propuesta).

Toda actividad cambia de lista por `mover_actividad` (o nace en una con `crear_actividad`), para que
ningún movimiento quede fuera del historial. Nunca se escribe `Actividad.lista` directamente.
"""

import mimetypes
import os
from contextlib import contextmanager, nullcontext

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import F, Sum

from apps.pizarras.models import Lista, MiembroPizarra, Pizarra, Solicitante, TipoActividad
from apps.pizarras.servicios import crear_solicitante, exigir_permiso

from .almacen import comprimir_pdf
from .models import Actividad, Adjunto, ElementoChecklist, Movimiento

CAMPOS_EDITABLES = (
    "titulo",
    "lista",
    "descripcion",
    "fecha_solicitud",
    "fecha_fin",
    "asignados",
    "tipos",
    "lista_terminado",
    "lista_al_completar",
    *("solicitada_por", "solicitante_externo", "solicitante_nuevo"),
)
CAMPOS_SOLICITANTE = ("solicitada_por", "solicitante_externo", "solicitante_nuevo")

# Elementos de la checklist (2026-10-06: antes 200). El título de una actividad sigue en 200: al
# convertir uno más largo, la PWA recorta el título y pone el texto completo en la descripción.
MAX_TEXTO_ELEMENTO = 400
MAX_TITULO = 200


# ---------------------------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------------------------


def _validar_asignados(pizarra: Pizarra, asignados) -> list:
    ids = {getattr(u, "pk", u) for u in (asignados or [])}
    miembros = set(
        MiembroPizarra.objects.filter(pizarra=pizarra, usuario_id__in=ids).values_list(
            "usuario_id", flat=True
        )
    )
    if ids - miembros:
        raise ValidationError({"asignados": "Solo se puede asignar a miembros de la pizarra."})
    return list(ids)


def _validar_tipos(pizarra: Pizarra, tipos) -> list:
    ids = {getattr(t, "pk", t) for t in (tipos or [])}
    de_la_pizarra = set(
        TipoActividad.objects.filter(pizarra=pizarra, pk__in=ids).values_list("pk", flat=True)
    )
    if ids - de_la_pizarra:
        raise ValidationError({"tipos": "Solo se pueden usar tipos de esta pizarra."})
    return list(ids)


def _validar_titulo(titulo) -> str:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValidationError({"titulo": "Escribe un título."})
    if len(titulo) > MAX_TITULO:
        raise ValidationError({"titulo": f"Máximo {MAX_TITULO} caracteres."})
    return titulo


def partir_titulo(texto: str, tope: int = MAX_TITULO) -> tuple[str, str]:
    """
    Título y resto de un texto largo (al convertir un elemento de la checklist, §4.7): corta en el
    último espacio antes del tope para no partir una palabra, salvo que eso dejara un título muy
    corto. El resto va a la descripción. Igual que `partirTitulo` de la PWA.
    """
    if len(texto) <= tope:
        return texto, ""
    corte = texto.rfind(" ", 0, tope + 1)
    if corte < tope * 0.6:
        corte = tope
    return texto[:corte].strip(), texto[corte:].strip()


def _validar_fechas(fecha_solicitud, fecha_fin) -> None:
    """Las dos son opcionales; solo si están las dos, «Vence el» no puede ser anterior."""
    if fecha_solicitud and fecha_fin and fecha_fin < fecha_solicitud:
        raise ValidationError({"fecha_fin": "No puede ser anterior a la fecha de solicitud."})


def _solicitante(pizarra: Pizarra, usuario, datos: dict, actual=None) -> tuple:
    """
    «Solicitada por» (§4.4): `solicitada_por` (id de un miembro), `solicitante_externo` (id del
    catálogo) o `solicitante_nuevo` (nombre: lo crea o reutiliza), a lo más uno; nada = sin
    solicitante. Devuelve `(usuario_id, solicitante_id)`. Un miembro que ya era el solicitante se
    conserva aunque haya salido de la pizarra.
    """
    miembro = datos.get("solicitada_por") or None
    externo = datos.get("solicitante_externo") or None
    nuevo = (datos.get("solicitante_nuevo") or "").strip()
    if sum(bool(x) for x in (miembro, externo, nuevo)) > 1:
        raise ValidationError({"solicitante": "Elige solo una persona."})
    if miembro:
        try:
            miembro = int(miembro)
        except (TypeError, ValueError) as e:
            raise ValidationError({"solicitante": "Solicitante inválido."}) from e
        ya_era = actual is not None and actual.solicitada_por_id == miembro
        if (
            not ya_era
            and not MiembroPizarra.objects.filter(pizarra=pizarra, usuario_id=miembro).exists()
        ):
            raise ValidationError({"solicitante": "Elige a un miembro de la pizarra."})
        return miembro, None
    if externo:
        s = (
            Solicitante.objects.filter(pizarra=pizarra, pk=externo).first()
            if str(externo).isdigit()
            else None
        )
        if s is None:
            raise ValidationError({"solicitante": "Elige un solicitante de esta pizarra."})
        return None, s.pk
    if nuevo:
        try:
            return None, crear_solicitante(pizarra, usuario, nuevo).pk
        except ValidationError as e:
            raise ValidationError({"solicitante": e.message_dict.get("nombre", e.messages)}) from e
    return None, None


def _lista_de(pizarra: Pizarra, lista) -> Lista:
    """La lista (objeto o id) debe ser de la pizarra."""
    pk = getattr(lista, "pk", lista)
    encontrada = Lista.objects.filter(pizarra=pizarra, pk=pk).first() if pk else None
    if encontrada is None:
        raise ValidationError({"lista": "Elige una lista de esta pizarra."})
    return encontrada


def registrar_movimiento(
    actividad: Actividad, usuario, anterior="", nueva="", nota=""
) -> Movimiento:
    """Una fila del historial. `anterior=""` y sin nota = creación. También la usa el admin."""
    return Movimiento.objects.create(
        actividad=actividad,
        usuario=usuario,
        lista_anterior=anterior or "",
        lista_nueva=nueva or "",
        nota=nota or "",
    )


def _renumerar(lista_id: int, orden: list[Actividad] | None = None) -> None:
    """Deja las posiciones de la lista en 0, 1, 2… (en `orden` o en el orden actual)."""
    actividades = orden if orden is not None else list(Actividad.objects.filter(lista_id=lista_id))
    cambiadas = []
    for posicion, t in enumerate(actividades):
        if t.posicion != posicion:
            t.posicion = posicion
            cambiadas.append(t)
    Actividad.objects.bulk_update(cambiadas, ["posicion"])


# ---------------------------------------------------------------------------------------------
# Actividades
# ---------------------------------------------------------------------------------------------


@transaction.atomic
def crear_actividad(
    pizarra: Pizarra,
    usuario,
    *,
    titulo: str,
    descripcion: str = "",
    lista=None,
    fecha_solicitud=None,
    fecha_fin=None,
    asignados=(),
    tipos=(),
    checklist=(),
    arriba=False,
    lista_al_completar=None,
    solicitada_por=None,
    solicitante_externo=None,
    solicitante_nuevo="",
) -> Actividad:
    """
    Nace al final de `lista` (por omisión, la primera de la pizarra), o arriba con `arriba` (el
    «+» del encabezado de la lista, §4.7), y queda en el historial. `checklist` son los textos de
    sus elementos: se capturan en el mismo formulario y van con el permiso «Crear».
    `lista_al_completar`: «Mover a [lista] al completar» la checklist (§4.7).
    """
    exigir_permiso(pizarra, usuario, "crear")
    titulo = _validar_titulo(titulo)
    if lista is None:
        lista = pizarra.listas.first()
        if lista is None:
            raise ValidationError({"lista": "La pizarra no tiene listas: crea una antes."})
    else:
        lista = _lista_de(pizarra, lista)
    _validar_fechas(fecha_solicitud, fecha_fin)
    ids_asignados = _validar_asignados(pizarra, asignados)
    ids_tipos = _validar_tipos(pizarra, tipos)
    textos = [_validar_texto(t) for t in (checklist or [])]
    al_completar = _lista_al_completar(pizarra, lista_al_completar)
    id_miembro, id_externo = _solicitante(
        pizarra,
        usuario,
        {
            "solicitada_por": solicitada_por,
            "solicitante_externo": solicitante_externo,
            "solicitante_nuevo": solicitante_nuevo,
        },
    )
    if arriba:
        lista.actividades.update(posicion=F("posicion") + 1)
        posicion = 0
    else:
        ultima = lista.actividades.order_by("-posicion").values_list("posicion", flat=True).first()
        posicion = 0 if ultima is None else ultima + 1
    actividad = Actividad.objects.create(
        pizarra=pizarra,
        lista=lista,
        posicion=posicion,
        titulo=titulo,
        descripcion=(descripcion or "").strip(),
        fecha_solicitud=fecha_solicitud,
        fecha_fin=fecha_fin,
        creada_por=usuario,
        lista_al_completar=al_completar,
        solicitada_por_id=id_miembro,
        solicitante_externo_id=id_externo,
    )
    actividad.asignados.set(ids_asignados)
    actividad.tipos.set(ids_tipos)
    ElementoChecklist.objects.bulk_create(
        ElementoChecklist(actividad=actividad, texto=texto, posicion=i)
        for i, texto in enumerate(textos)
    )
    registrar_movimiento(actividad, usuario, nueva=lista.nombre)
    return actividad


@transaction.atomic
def editar_actividad(actividad: Actividad, usuario, **campos) -> Actividad:
    """
    Edita los datos de la actividad. Una `lista` distinta la mueve al final de esa lista con
    `mover_actividad` (pide también el permiso «Mover» y queda en el historial): el formulario de
    edición tiene los mismos campos que el de alta (§4.7). La posición solo cambia arrastrando.
    Si al cambiar `lista_terminado` la checklist queda completa, aplica `lista_al_completar`.
    """
    exigir_permiso(actividad.pizarra, usuario, "editar")
    with _al_completar(actividad.pk, usuario):
        _editar_actividad(actividad, usuario, campos)
    actividad.refresh_from_db()
    return actividad


def _editar_actividad(actividad: Actividad, usuario, campos) -> None:
    desconocidos = set(campos) - set(CAMPOS_EDITABLES)
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    if "titulo" in campos:
        actividad.titulo = _validar_titulo(campos["titulo"])
        # Si viene de una checklist, su elemento dice lo mismo que su título (§4.7).
        ElementoChecklist.objects.filter(actividad_creada=actividad).exclude(
            texto=actividad.titulo
        ).update(texto=actividad.titulo)
    if "descripcion" in campos:
        actividad.descripcion = (campos["descripcion"] or "").strip()
    if "fecha_solicitud" in campos:
        actividad.fecha_solicitud = campos["fecha_solicitud"]
    if "fecha_fin" in campos:
        actividad.fecha_fin = campos["fecha_fin"]
    _validar_fechas(actividad.fecha_solicitud, actividad.fecha_fin)
    nueva_lista = None
    if campos.get("lista") is not None:
        nueva_lista = _lista_de(actividad.pizarra, campos["lista"])
        if nueva_lista.pk == actividad.lista_id:
            nueva_lista = None
        else:
            exigir_permiso(actividad.pizarra, usuario, "mover")
    if "lista_terminado" in campos:
        _fijar_lista_terminado(actividad, campos["lista_terminado"])
    if any(c in campos for c in CAMPOS_SOLICITANTE):
        actividad.solicitada_por_id, actividad.solicitante_externo_id = _solicitante(
            actividad.pizarra, usuario, campos, actual=actividad
        )
    if "lista_al_completar" in campos:
        actividad.lista_al_completar = _lista_al_completar(
            actividad.pizarra, campos["lista_al_completar"]
        )
    actividad.save()
    if "asignados" in campos:
        actividad.asignados.set(_validar_asignados(actividad.pizarra, campos["asignados"]))
    if "tipos" in campos:
        actividad.tipos.set(_validar_tipos(actividad.pizarra, campos["tipos"]))
    if nueva_lista is not None:
        mover_actividad(actividad, usuario, nueva_lista)


@transaction.atomic
def mover_actividad(actividad: Actividad, usuario, lista, posicion=None) -> Actividad:
    """
    Pone la actividad en `lista` (de la misma pizarra) en `posicion` (0 = arriba; None = al final)
    y renumera las listas afectadas. Cambiar de lista queda en el historial; reordenar dentro de
    la misma lista no (sería ruido, §4.6).
    """
    exigir_permiso(actividad.pizarra, usuario, "mover")
    return _mover(actividad, usuario, lista, posicion)


def _mover(actividad: Actividad, usuario, lista, posicion=None) -> Actividad:
    """
    `mover_actividad` sin revisar el permiso: también lo usa «Mover a … al completar», que decidió
    quien eligió la lista (§4.7). Si la actividad viene de la checklist de otra, moverla puede
    palomear su elemento y completar esa checklist: entonces la otra también se mueve (y así hacia
    arriba, si a su vez viene de otra checklist).
    """
    padre = (
        ElementoChecklist.objects.filter(actividad_creada_id=actividad.pk)
        .values_list("actividad_id", flat=True)
        .first()
    )
    with _al_completar(padre, usuario) if padre else nullcontext():
        return _mover_sin_cascada(actividad, usuario, lista, posicion)


def _mover_sin_cascada(actividad: Actividad, usuario, lista, posicion) -> Actividad:
    destino = _lista_de(actividad.pizarra, lista)
    # Bloquea la actividad: dos personas moviéndola a la vez dejan un historial coherente.
    actual = Actividad.objects.select_for_update().select_related("lista").get(pk=actividad.pk)
    origen = actual.lista
    hermanas = list(
        Actividad.objects.select_for_update().filter(lista=destino).exclude(pk=actual.pk)
    )
    if posicion is None:
        posicion = len(hermanas)
    try:
        posicion = max(0, min(int(posicion), len(hermanas)))
    except (TypeError, ValueError) as e:
        raise ValidationError({"posicion": "Posición inválida."}) from e
    actual.lista = destino
    hermanas.insert(posicion, actual)
    actual.save(update_fields=["lista", "actualizado_en"])
    actual.posicion = -1  # fuerza que _renumerar la guarde
    _renumerar(destino.pk, hermanas)
    if origen.pk != destino.pk:
        _renumerar(origen.pk)
        registrar_movimiento(actual, usuario, origen.nombre, destino.nombre)
    actividad.lista, actividad.posicion = actual.lista, actual.posicion
    return actual


@transaction.atomic
def eliminar_actividad(actividad: Actividad, usuario) -> None:
    """
    Borra la actividad con su historial y su checklist (CASCADE). Si venía de la checklist de otra,
    ese elemento vuelve a ser texto y conserva si estaba hecho.
    """
    exigir_permiso(actividad.pizarra, usuario, "eliminar")
    origen = ElementoChecklist.objects.filter(actividad_creada=actividad).first()
    if origen:
        origen.hecho = _hecho_ahora(origen)
        origen.actividad_creada = None
        origen.save(update_fields=["hecho", "actividad_creada", "actualizado_en"])
    lista_id = actividad.lista_id
    actividad.delete()
    _renumerar(lista_id)


# ---------------------------------------------------------------------------------------------
# Checklist (§4.6): palomear, agregar, editar, ordenar y quitar = permiso «editar»;
# convertir un elemento en actividad enlazada = permiso «crear».
# ---------------------------------------------------------------------------------------------


def _hecho_ahora(elemento: ElementoChecklist) -> bool:
    """Como `esta_hecho`, pero leyendo de la base dónde está hoy la actividad enlazada y la lista de
    terminado de la suya (los objetos en memoria pueden traer datos viejos)."""
    if not elemento.actividad_creada_id:
        return elemento.hecho
    terminado = (
        Actividad.objects.filter(pk=elemento.actividad_id)
        .values_list("lista_terminado_id", flat=True)
        .first()
    )
    if not terminado:
        return elemento.hecho
    lista_id = (
        Actividad.objects.filter(pk=elemento.actividad_creada_id)
        .values_list("lista_id", flat=True)
        .first()
    )
    return lista_id == terminado


def _cita(texto: str, largo: int = 200) -> str:
    """Para citar un elemento en una nota del historial (300 caracteres): los elementos llegan a
    400 desde la Etapa 3.8."""
    return texto if len(texto) <= largo else texto[: largo - 1].rstrip() + "…"


def _checklist_completa(actividad_id) -> bool:
    elementos = list(ElementoChecklist.objects.filter(actividad_id=actividad_id))
    return bool(elementos) and all(_hecho_ahora(e) for e in elementos)


@contextmanager
def _al_completar(actividad_id, usuario):
    """
    «Mover a [lista] al completar» (§4.7): si dentro del bloque la checklist de la actividad pasa
    de incompleta a completa, la mueve al final de su `lista_al_completar` (si no estaba ya ahí).
    Solo en esa transición: despalomear después no la regresa, y elegir la lista con la checklist
    ya completa no la mueve.
    """
    antes = _checklist_completa(actividad_id)
    yield
    if antes:
        return
    actividad = Actividad.objects.filter(pk=actividad_id).first()
    if (
        actividad
        and actividad.lista_al_completar_id
        and actividad.lista_al_completar_id != actividad.lista_id
        and _checklist_completa(actividad_id)
    ):
        _mover(actividad, usuario, actividad.lista_al_completar_id)


def _lista_al_completar(pizarra: Pizarra, lista):
    if lista in (None, ""):
        return None
    try:
        return _lista_de(pizarra, lista)
    except ValidationError as e:
        raise ValidationError({"lista_al_completar": "Elige una lista de esta pizarra."}) from e


def _fijar_lista_terminado(actividad: Actividad, lista) -> None:
    """
    «Lo que llega a [lista] cuenta como terminado» de la checklist de `actividad` (2026-10-06).
    No puede ser la lista donde está la propia actividad: sus hijas nacen ahí y se darían por
    hechas al crearlas. Vacía = palomeo manual; cada elemento conserva el estado que tenía.
    """
    if lista in (None, ""):
        if actividad.lista_terminado_id:
            for e in actividad.checklist.filter(actividad_creada__isnull=False):
                e.hecho = _hecho_ahora(e)
                e.save(update_fields=["hecho", "actualizado_en"])
        actividad.lista_terminado = None
        return
    try:
        destino = _lista_de(actividad.pizarra, lista)
    except ValidationError as e:
        raise ValidationError({"lista_terminado": "Elige una lista de esta pizarra."}) from e
    if destino.pk == actividad.lista_id:
        raise ValidationError(
            {"lista_terminado": "Elige una lista distinta de la que tiene esta actividad."}
        )
    actividad.lista_terminado = destino


def _validar_texto(texto) -> str:
    texto = (texto or "").strip()
    if not texto:
        raise ValidationError({"texto": "Escribe el elemento."})
    if len(texto) > MAX_TEXTO_ELEMENTO:
        raise ValidationError({"texto": f"Máximo {MAX_TEXTO_ELEMENTO} caracteres."})
    return texto


@transaction.atomic
def agregar_elemento(actividad: Actividad, usuario, texto: str) -> ElementoChecklist:
    exigir_permiso(actividad.pizarra, usuario, "editar")
    ultima = actividad.checklist.order_by("-posicion").values_list("posicion", flat=True).first()
    return ElementoChecklist.objects.create(
        actividad=actividad,
        texto=_validar_texto(texto),
        posicion=0 if ultima is None else ultima + 1,
    )


@transaction.atomic
def editar_elemento(elemento: ElementoChecklist, usuario, **campos) -> ElementoChecklist:
    """
    Cambia `texto` o `hecho` (solo si se palomea a mano). La lista en la que un elemento
    convertido se da por hecho es de toda la actividad: `editar_actividad(lista_terminado=…)`.
    Palomear el último pendiente aplica «Mover a … al completar».
    """
    pizarra = elemento.actividad.pizarra
    exigir_permiso(pizarra, usuario, "editar")
    desconocidos = set(campos) - {"texto", "hecho"}
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    with _al_completar(elemento.actividad_id, usuario):
        if "texto" in campos:
            if elemento.actividad_creada_id:
                mensaje = "Este elemento es una actividad: cambia el título de esa actividad."
                raise ValidationError({"texto": mensaje})
            elemento.texto = _validar_texto(campos["texto"])
        if "hecho" in campos:
            if elemento.automatico:
                mensaje = (
                    "Este elemento se marca solo cuando su actividad llega a la lista elegida."
                )
                raise ValidationError({"hecho": mensaje})
            elemento.hecho = bool(campos["hecho"])
        elemento.save()
    return elemento


@transaction.atomic
def ordenar_checklist(actividad: Actividad, usuario, ids: list[int]) -> None:
    """`ids` = todos los elementos de la checklist en el orden nuevo."""
    exigir_permiso(actividad.pizarra, usuario, "editar")
    elementos = {e.pk: e for e in actividad.checklist.select_for_update()}
    try:
        ids = [int(i) for i in ids or []]
    except (TypeError, ValueError) as e:
        raise ValidationError({"ids": "Orden inválido."}) from e
    if sorted(ids) != sorted(elementos):
        raise ValidationError({"ids": "El orden debe incluir todos los elementos."})
    for posicion, pk in enumerate(ids):
        elementos[pk].posicion = posicion
    ElementoChecklist.objects.bulk_update(elementos.values(), ["posicion"])


@transaction.atomic
def quitar_elemento(elemento: ElementoChecklist, usuario) -> None:
    """
    Si era actividad, la actividad se queda (solo pierde el «Viene de»). Quitar el último pendiente
    completa la checklist y aplica «Mover a … al completar».
    """
    exigir_permiso(elemento.actividad.pizarra, usuario, "editar")
    with _al_completar(elemento.actividad_id, usuario):
        elemento.delete()


@transaction.atomic
def convertir_elemento(elemento: ElementoChecklist, usuario, **datos) -> Actividad:
    """
    Crea una actividad en la misma pizarra a partir del elemento y las enlaza (§4.6). `datos` son
    los de `crear_actividad` (el título por omisión es el texto del elemento). Se da por hecho
    según la `lista_terminado` de la actividad de la checklist (o se palomea a mano si no tiene).
    """
    padre = elemento.actividad
    pizarra = padre.pizarra
    exigir_permiso(pizarra, usuario, "crear")
    if elemento.actividad_creada_id:
        raise ValidationError("Este elemento ya se convirtió en actividad.")
    if "titulo" not in datos:
        titulo, resto = partir_titulo(elemento.texto)
        datos["titulo"] = titulo
        if resto:
            datos.setdefault("descripcion", resto)
    datos.setdefault("lista", padre.lista)
    # Si la nueva nace en la lista de terminado, el elemento queda hecho y puede completar la
    # checklist.
    texto_original = elemento.texto
    with _al_completar(padre.pk, usuario):
        nueva = crear_actividad(pizarra, usuario, **datos)
        # Desde aquí el elemento dice lo mismo que el título de su actividad, y lo sigue al
        # editarlo (`editar_actividad`). Lo que no cupo en el título va en la descripción (PWA).
        elemento.actividad_creada = nueva
        elemento.texto = nueva.titulo
        elemento.save(update_fields=["actividad_creada", "texto", "actualizado_en"])
    registrar_movimiento(
        padre, usuario, nota=f"convirtió «{_cita(texto_original)}» de la checklist en actividad"
    )
    registrar_movimiento(nueva, usuario, nota=f"la creó desde la checklist de «{padre.titulo}»")
    return nueva


# ---------------------------------------------------------------------------------------------
# Adjuntos (Etapa 3.8, §4.4): adjuntar y quitar = permiso «Editar»; descargar, cualquier miembro.
# ---------------------------------------------------------------------------------------------

MB = 1024 * 1024


def espacio_adjuntos(pizarra: Pizarra) -> int:
    """Bytes que ocupan los adjuntos de la pizarra (ya comprimidos)."""
    return Adjunto.objects.filter(actividad__pizarra=pizarra).aggregate(t=Sum("tamano"))["t"] or 0


def _nombre_archivo(nombre) -> str:
    nombre = os.path.basename(str(nombre or "")).strip().replace("\x00", "")
    if not nombre:
        return "archivo"
    if len(nombre) > 255:
        raiz, extension = os.path.splitext(nombre)
        nombre = raiz[: 255 - len(extension[:20])] + extension[:20]
    return nombre


def _mb(n: int) -> str:
    return f"{n / MB:.1f}".rstrip("0").rstrip(".") + " MB"


@transaction.atomic
def adjuntar(actividad: Actividad, usuario, archivo) -> Adjunto:
    """
    Guarda `archivo` (un `UploadedFile`) en la actividad. Cualquier tipo de archivo; hasta
    `TASKFLOW_ADJUNTO_MAX_MB` cada uno y `TASKFLOW_ADJUNTOS_PIZARRA_MB` por pizarra. Un PDF de más
    de `TASKFLOW_PDF_COMPRIMIR_DESDE_MB` se comprime y se guarda el más chico de los dos.
    """
    pizarra = actividad.pizarra
    exigir_permiso(pizarra, usuario, "editar")
    if archivo is None:
        raise ValidationError({"archivo": "Elige un archivo."})
    maximo = settings.TASKFLOW_ADJUNTO_MAX_MB * MB
    if archivo.size > maximo:
        raise ValidationError({"archivo": f"El archivo pasa de {_mb(maximo)}."})
    nombre = _nombre_archivo(archivo.name)
    tipo = mimetypes.guess_type(nombre)[0] or "application/octet-stream"
    contenido = archivo.read()
    if contenido[:5] == b"%PDF-" and len(contenido) > settings.TASKFLOW_PDF_COMPRIMIR_DESDE_MB * MB:
        comprimido = comprimir_pdf(contenido)
        if comprimido and comprimido[:5] == b"%PDF-" and len(comprimido) < len(contenido):
            contenido = comprimido
    # Bloquea la pizarra: dos subidas a la vez no deben pasar juntas del tope.
    Pizarra.objects.select_for_update().filter(pk=pizarra.pk).first()
    limite = settings.TASKFLOW_ADJUNTOS_PIZARRA_MB * MB
    usado = espacio_adjuntos(pizarra)
    if usado + len(contenido) > limite:
        libre = max(limite - usado, 0)
        raise ValidationError(
            {"archivo": f"La pizarra llegó a su límite de {_mb(limite)} (quedan {_mb(libre)})."}
        )
    adjunto = Adjunto(
        actividad=actividad, nombre=nombre, tamano=len(contenido), tipo=tipo, subido_por=usuario
    )
    adjunto.archivo.save(nombre, ContentFile(contenido), save=False)
    adjunto.save()
    return adjunto


def quitar_adjunto(adjunto: Adjunto, usuario) -> None:
    """Borra la fila y, al confirmar la transacción, el archivo (señal en `models.py`)."""
    exigir_permiso(adjunto.actividad.pizarra, usuario, "editar")
    adjunto.delete()
