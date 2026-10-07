/**
 * Arrastrar y soltar (§4.6) con SortableJS, como directiva: `v-arrastrable="{ grupo, alSoltar }"`.
 *
 * - Computadora: se arrastra con el mouse al instante.
 * - Teléfono: hay que mantener presionado ~0.35 s (`delayOnTouchOnly`); si el dedo se mueve antes,
 *   es un desplazamiento normal. La actividad se levanta con una vibración breve y cerca de los
 *   bordes la pantalla y el tablero se desplazan solos (`scroll`, `bubbleScroll`).
 * - SortableJS mueve el nodo en el DOM; al soltar se devuelve a su lugar y se avisa con
 *   `alSoltar`: quien la usa actualiza sus datos y Vue vuelve a pintar. Así el DOM nunca se
 *   desincroniza de lo que Vue cree que hay (lo mismo que hace vuedraggable por dentro).
 */
import Sortable from "sortablejs";
import type { Directive } from "vue";

export interface Soltado {
  /** `data-id` del elemento arrastrado. */
  id: number;
  /** Contenedor donde cayó (su `data-*` dice qué lista es). */
  destino: HTMLElement;
  /** `data-id` del elemento que quedó justo después, o null si quedó al final. */
  antesDe: number | null;
}

export interface OpcionesArrastre {
  /** Contenedores con el mismo grupo intercambian elementos (las listas de un tablero). */
  grupo: string;
  alSoltar: (s: Soltado) => void;
  /** false = no se puede arrastrar (sin permiso o pizarra archivada). */
  activo?: boolean;
  /** Solo se arrastra desde este selector (p. ej. la manija de un elemento de checklist). */
  manija?: string;
}

const ESPERA_TACTIL_MS = 350;

// Soltar una actividad no debe abrir su detalle: se ignora el clic que llega justo después.
let finDelArrastre = 0;
document.addEventListener(
  "click",
  (e) => {
    if (Date.now() - finDelArrastre < 350) {
      e.stopPropagation();
      e.preventDefault();
    }
  },
  true,
);

function crear(el: HTMLElement, opciones: OpcionesArrastre): Sortable {
  let siguienteOriginal: Node | null = null;
  return Sortable.create(el, {
    group: opciones.grupo,
    draggable: "[data-id]",
    handle: opciones.manija,
    disabled: opciones.activo === false,
    animation: 150,
    delay: ESPERA_TACTIL_MS,
    delayOnTouchOnly: true,
    touchStartThreshold: 8,
    // Arrastre propio (no el nativo del navegador): igual en teléfono y computadora, y permite
    // dar estilo a la actividad levantada (.fantasma) y al hueco que deja (.hueco).
    forceFallback: true,
    fallbackOnBody: true,
    fallbackTolerance: 4,
    ghostClass: "hueco",
    chosenClass: "elegida",
    dragClass: "fantasma",
    scroll: true,
    bubbleScroll: true,
    scrollSensitivity: 70,
    scrollSpeed: 14,
    onChoose() {
      navigator.vibrate?.(15);
    },
    onStart(evt) {
      siguienteOriginal = evt.item.nextSibling;
    },
    onEnd(evt) {
      finDelArrastre = Date.now();
      const { item, from, to } = evt;
      let siguiente = item.nextElementSibling;
      while (siguiente && !(siguiente as HTMLElement).dataset.id) siguiente = siguiente.nextElementSibling;
      const antesDe = siguiente ? Number((siguiente as HTMLElement).dataset.id) : null;
      const cambio = from !== to || evt.oldIndex !== evt.newIndex;
      from.insertBefore(item, siguienteOriginal); // de vuelta a donde estaba: Vue repinta
      if (cambio) opciones.alSoltar({ id: Number(item.dataset.id), destino: to, antesDe });
    },
  });
}

const instancias = new WeakMap<HTMLElement, { sortable: Sortable; opciones: OpcionesArrastre }>();

export const vArrastrable: Directive<HTMLElement, OpcionesArrastre> = {
  mounted(el, { value }) {
    // Las opciones se leen al soltar, para que `alSoltar` siempre vea los datos actuales.
    const registro = { sortable: null as unknown as Sortable, opciones: value };
    registro.sortable = crear(el, {
      ...value,
      alSoltar: (s) => registro.opciones.alSoltar(s),
    });
    instancias.set(el, registro);
  },
  updated(el, { value }) {
    const registro = instancias.get(el);
    if (!registro) return;
    registro.opciones = value;
    registro.sortable.option("disabled", value.activo === false);
  },
  unmounted(el) {
    instancias.get(el)?.sortable.destroy();
    instancias.delete(el);
  },
};
