"""
Reglas de negocio de las tarjetas y su checklist (§4.6 de la propuesta).

Toda tarjeta cambia de lista por `mover_tarjeta` (o nace en una con `crear_tarjeta`), para que
ningún movimiento quede fuera del historial. Nunca se escribe `Tarjeta.lista` directamente.
"""

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.pizarras.models import Lista, MiembroPizarra, Pizarra, TipoTarjeta
from apps.pizarras.servicios import exigir_permiso

from .models import ElementoChecklist, Movimiento, Prioridad, Tarjeta, hoy

CAMPOS_EDITABLES = (
    "titulo",
    "descripcion",
    "prioridad",
    "fecha_inicio",
    "fecha_fin",
    "asignados",
    "tipos",
    "lista_terminado",
)


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
        TipoTarjeta.objects.filter(pizarra=pizarra, pk__in=ids).values_list("pk", flat=True)
    )
    if ids - de_la_pizarra:
        raise ValidationError({"tipos": "Solo se pueden usar tipos de esta pizarra."})
    return list(ids)


def _validar_titulo(titulo) -> str:
    titulo = (titulo or "").strip()
    if not titulo:
        raise ValidationError({"titulo": "Escribe un título."})
    return titulo


def _validar_prioridad(prioridad: str) -> str:
    if prioridad not in Prioridad.values:
        raise ValidationError({"prioridad": "Prioridad inválida."})
    return prioridad


def _validar_fechas(fecha_inicio, fecha_fin) -> None:
    if fecha_inicio is None:
        raise ValidationError({"fecha_inicio": "Escribe la fecha de inicio."})
    if fecha_fin and fecha_fin < fecha_inicio:
        raise ValidationError({"fecha_fin": "No puede ser anterior a la fecha de inicio."})


def _lista_de(pizarra: Pizarra, lista) -> Lista:
    """La lista (objeto o id) debe ser de la pizarra."""
    pk = getattr(lista, "pk", lista)
    encontrada = Lista.objects.filter(pizarra=pizarra, pk=pk).first() if pk else None
    if encontrada is None:
        raise ValidationError({"lista": "Elige una lista de esta pizarra."})
    return encontrada


def registrar_movimiento(tarjeta: Tarjeta, usuario, anterior="", nueva="", nota="") -> Movimiento:
    """Una fila del historial. `anterior=""` y sin nota = creación. También la usa el admin."""
    return Movimiento.objects.create(
        tarjeta=tarjeta,
        usuario=usuario,
        lista_anterior=anterior or "",
        lista_nueva=nueva or "",
        nota=nota or "",
    )


def _renumerar(lista_id: int, orden: list[Tarjeta] | None = None) -> None:
    """Deja las posiciones de la lista en 0, 1, 2… (en `orden` o en el orden actual)."""
    tarjetas = orden if orden is not None else list(Tarjeta.objects.filter(lista_id=lista_id))
    cambiadas = []
    for posicion, t in enumerate(tarjetas):
        if t.posicion != posicion:
            t.posicion = posicion
            cambiadas.append(t)
    Tarjeta.objects.bulk_update(cambiadas, ["posicion"])


# ---------------------------------------------------------------------------------------------
# Tarjetas
# ---------------------------------------------------------------------------------------------


@transaction.atomic
def crear_tarjeta(
    pizarra: Pizarra,
    usuario,
    *,
    titulo: str,
    descripcion: str = "",
    lista=None,
    prioridad: str = Prioridad.MEDIA,
    fecha_inicio=None,
    fecha_fin=None,
    asignados=(),
    tipos=(),
) -> Tarjeta:
    """Nace al final de `lista` (por omisión, la primera de la pizarra) y queda en el historial."""
    exigir_permiso(pizarra, usuario, "crear")
    titulo = _validar_titulo(titulo)
    if lista is None:
        lista = pizarra.listas.first()
        if lista is None:
            raise ValidationError({"lista": "La pizarra no tiene listas: crea una antes."})
    else:
        lista = _lista_de(pizarra, lista)
    fecha_inicio = fecha_inicio or hoy()
    _validar_fechas(fecha_inicio, fecha_fin)
    ids_asignados = _validar_asignados(pizarra, asignados)
    ids_tipos = _validar_tipos(pizarra, tipos)
    ultima = lista.tarjetas.order_by("-posicion").values_list("posicion", flat=True).first()
    tarjeta = Tarjeta.objects.create(
        pizarra=pizarra,
        lista=lista,
        posicion=0 if ultima is None else ultima + 1,
        titulo=titulo,
        descripcion=(descripcion or "").strip(),
        prioridad=_validar_prioridad(prioridad),
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        creada_por=usuario,
    )
    tarjeta.asignados.set(ids_asignados)
    tarjeta.tipos.set(ids_tipos)
    registrar_movimiento(tarjeta, usuario, nueva=lista.nombre)
    return tarjeta


@transaction.atomic
def editar_tarjeta(tarjeta: Tarjeta, usuario, **campos) -> Tarjeta:
    """Edita los datos de la tarjeta (no su lista ni su posición: eso es `mover_tarjeta`)."""
    exigir_permiso(tarjeta.pizarra, usuario, "editar")
    desconocidos = set(campos) - set(CAMPOS_EDITABLES)
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    if "titulo" in campos:
        tarjeta.titulo = _validar_titulo(campos["titulo"])
    if "descripcion" in campos:
        tarjeta.descripcion = (campos["descripcion"] or "").strip()
    if "prioridad" in campos:
        tarjeta.prioridad = _validar_prioridad(campos["prioridad"])
    if "fecha_inicio" in campos:
        tarjeta.fecha_inicio = campos["fecha_inicio"]
    if "fecha_fin" in campos:
        tarjeta.fecha_fin = campos["fecha_fin"]
    _validar_fechas(tarjeta.fecha_inicio, tarjeta.fecha_fin)
    if "lista_terminado" in campos:
        _fijar_lista_terminado(tarjeta, campos["lista_terminado"])
    tarjeta.save()
    if "asignados" in campos:
        tarjeta.asignados.set(_validar_asignados(tarjeta.pizarra, campos["asignados"]))
    if "tipos" in campos:
        tarjeta.tipos.set(_validar_tipos(tarjeta.pizarra, campos["tipos"]))
    return tarjeta


@transaction.atomic
def mover_tarjeta(tarjeta: Tarjeta, usuario, lista, posicion=None) -> Tarjeta:
    """
    Pone la tarjeta en `lista` (de la misma pizarra) en `posicion` (0 = arriba; None = al final)
    y renumera las listas afectadas. Cambiar de lista queda en el historial; reordenar dentro de
    la misma lista no (sería ruido, §4.6).
    """
    exigir_permiso(tarjeta.pizarra, usuario, "mover")
    destino = _lista_de(tarjeta.pizarra, lista)
    # Bloquea la tarjeta: dos personas moviéndola a la vez dejan un historial coherente.
    actual = Tarjeta.objects.select_for_update().select_related("lista").get(pk=tarjeta.pk)
    origen = actual.lista
    hermanas = list(Tarjeta.objects.select_for_update().filter(lista=destino).exclude(pk=actual.pk))
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
    tarjeta.lista, tarjeta.posicion = actual.lista, actual.posicion
    return actual


@transaction.atomic
def eliminar_tarjeta(tarjeta: Tarjeta, usuario) -> None:
    """
    Borra la tarjeta con su historial y su checklist (CASCADE). Si venía de la checklist de otra,
    ese elemento vuelve a ser texto y conserva si estaba hecho.
    """
    exigir_permiso(tarjeta.pizarra, usuario, "eliminar")
    origen = ElementoChecklist.objects.filter(tarjeta_creada=tarjeta).first()
    if origen:
        origen.hecho = _hecho_ahora(origen)
        origen.tarjeta_creada = None
        origen.save(update_fields=["hecho", "tarjeta_creada", "actualizado_en"])
    lista_id = tarjeta.lista_id
    tarjeta.delete()
    _renumerar(lista_id)


# ---------------------------------------------------------------------------------------------
# Checklist (§4.6): palomear, agregar, editar, ordenar y quitar = permiso «editar»;
# convertir un elemento en tarjeta enlazada = permiso «crear».
# ---------------------------------------------------------------------------------------------


def _hecho_ahora(elemento: ElementoChecklist) -> bool:
    """Como `esta_hecho`, pero leyendo de la base dónde está hoy la tarjeta enlazada y la lista de
    terminado de la suya (los objetos en memoria pueden traer datos viejos)."""
    if not elemento.tarjeta_creada_id:
        return elemento.hecho
    terminado = (
        Tarjeta.objects.filter(pk=elemento.tarjeta_id)
        .values_list("lista_terminado_id", flat=True)
        .first()
    )
    if not terminado:
        return elemento.hecho
    lista_id = (
        Tarjeta.objects.filter(pk=elemento.tarjeta_creada_id)
        .values_list("lista_id", flat=True)
        .first()
    )
    return lista_id == terminado


def _fijar_lista_terminado(tarjeta: Tarjeta, lista) -> None:
    """
    «Lo que llega a [lista] cuenta como terminado» de la checklist de `tarjeta` (2026-10-06).
    No puede ser la lista donde está la propia tarjeta: sus tarjetas hijas nacen ahí y se darían
    por hechas al crearlas. Vacía = palomeo manual; cada elemento conserva el estado que tenía.
    """
    if lista in (None, ""):
        if tarjeta.lista_terminado_id:
            for e in tarjeta.checklist.filter(tarjeta_creada__isnull=False):
                e.hecho = _hecho_ahora(e)
                e.save(update_fields=["hecho", "actualizado_en"])
        tarjeta.lista_terminado = None
        return
    try:
        destino = _lista_de(tarjeta.pizarra, lista)
    except ValidationError as e:
        raise ValidationError({"lista_terminado": "Elige una lista de esta pizarra."}) from e
    if destino.pk == tarjeta.lista_id:
        raise ValidationError(
            {"lista_terminado": "Elige una lista distinta de la que tiene esta tarjeta."}
        )
    tarjeta.lista_terminado = destino


def _validar_texto(texto) -> str:
    texto = (texto or "").strip()
    if not texto:
        raise ValidationError({"texto": "Escribe el elemento."})
    if len(texto) > 200:
        raise ValidationError({"texto": "Máximo 200 caracteres."})
    return texto


@transaction.atomic
def agregar_elemento(tarjeta: Tarjeta, usuario, texto: str) -> ElementoChecklist:
    exigir_permiso(tarjeta.pizarra, usuario, "editar")
    ultima = tarjeta.checklist.order_by("-posicion").values_list("posicion", flat=True).first()
    return ElementoChecklist.objects.create(
        tarjeta=tarjeta, texto=_validar_texto(texto), posicion=0 if ultima is None else ultima + 1
    )


@transaction.atomic
def editar_elemento(elemento: ElementoChecklist, usuario, **campos) -> ElementoChecklist:
    """
    Cambia `texto` o `hecho` (solo si se palomea a mano). La lista en la que un elemento
    convertido se da por hecho es de toda la tarjeta: `editar_tarjeta(lista_terminado=…)`.
    """
    pizarra = elemento.tarjeta.pizarra
    exigir_permiso(pizarra, usuario, "editar")
    desconocidos = set(campos) - {"texto", "hecho"}
    if desconocidos:
        raise ValidationError(f"Campos no editables: {', '.join(sorted(desconocidos))}.")
    if "texto" in campos:
        elemento.texto = _validar_texto(campos["texto"])
    if "hecho" in campos:
        if elemento.automatico:
            raise ValidationError(
                {"hecho": "Este elemento se marca solo cuando su tarjeta llega a la lista elegida."}
            )
        elemento.hecho = bool(campos["hecho"])
    elemento.save()
    return elemento


@transaction.atomic
def ordenar_checklist(tarjeta: Tarjeta, usuario, ids: list[int]) -> None:
    """`ids` = todos los elementos de la checklist en el orden nuevo."""
    exigir_permiso(tarjeta.pizarra, usuario, "editar")
    elementos = {e.pk: e for e in tarjeta.checklist.select_for_update()}
    try:
        ids = [int(i) for i in ids or []]
    except (TypeError, ValueError) as e:
        raise ValidationError({"ids": "Orden inválido."}) from e
    if sorted(ids) != sorted(elementos):
        raise ValidationError({"ids": "El orden debe incluir todos los elementos."})
    for posicion, pk in enumerate(ids):
        elementos[pk].posicion = posicion
    ElementoChecklist.objects.bulk_update(elementos.values(), ["posicion"])


def quitar_elemento(elemento: ElementoChecklist, usuario) -> None:
    """Si era tarjeta, la tarjeta se queda (solo pierde el «Viene de»)."""
    exigir_permiso(elemento.tarjeta.pizarra, usuario, "editar")
    elemento.delete()


@transaction.atomic
def convertir_elemento(elemento: ElementoChecklist, usuario, **datos) -> Tarjeta:
    """
    Crea una tarjeta en la misma pizarra a partir del elemento y las enlaza (§4.6). `datos` son
    los de `crear_tarjeta` (el título por omisión es el texto del elemento). Se da por hecho
    según la `lista_terminado` de la tarjeta de la checklist (o se palomea a mano si no tiene).
    """
    padre = elemento.tarjeta
    pizarra = padre.pizarra
    exigir_permiso(pizarra, usuario, "crear")
    if elemento.tarjeta_creada_id:
        raise ValidationError("Este elemento ya se convirtió en tarjeta.")
    datos.setdefault("titulo", elemento.texto)
    datos.setdefault("lista", padre.lista)
    nueva = crear_tarjeta(pizarra, usuario, **datos)
    elemento.tarjeta_creada = nueva
    elemento.save(update_fields=["tarjeta_creada", "actualizado_en"])
    registrar_movimiento(
        padre, usuario, nota=f"convirtió «{elemento.texto}» de la checklist en tarjeta"
    )
    registrar_movimiento(nueva, usuario, nota=f"la creó desde la checklist de «{padre.titulo}»")
    return nueva
