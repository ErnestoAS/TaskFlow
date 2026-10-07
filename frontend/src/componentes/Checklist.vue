<!--
  Checklist del detalle de una actividad (§4.6). Palomear, agregar, ordenar (arrastrando la manija) y
  quitar: permiso «Editar». Convertir un elemento en actividad enlazada: permiso «Crear» (lo hace
  PanelActividad con el formulario). Un elemento convertido muestra en qué lista está su actividad.
  Si hay alguno, debajo va «Lo que llega a [lista] cuenta como terminado» (2026-10-06): una lista
  para toda la checklist, distinta de la de esta actividad; con ella, los convertidos se palomean
  solos. «Ninguna» = a mano.
  También va dentro del formulario de edición (Etapa 3.8), con `sinConvertir`: convertir abre otro
  formulario. Por eso agregar no es un <form> (no se anidan) sino Enter o el botón.
  Etapa 3.8: el texto de un elemento se edita tocándolo (Enter o salir guarda, Esc cancela; los
  convertidos no, porque tocarlos abre su actividad), hasta 400 caracteres; un ícono copia la
  checklist como texto, y junto al título va «Al completar, mover a [lista]».
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { vArrastrable, type Soltado } from "../arrastre";
import type { ElementoChecklist, PizarraDetalle, Actividad } from "../tipos";
import { avisar } from "../ui";
import { copiarTexto, MAX_TEXTO_ELEMENTO, textoChecklist } from "../utilidades";
import Icono from "./Icono.vue";

const props = defineProps<{ actividad: Actividad; pizarra: PizarraDetalle; sinConvertir?: boolean }>();
const emit = defineEmits<{
  actualizada: [t: Actividad];
  convertir: [e: ElementoChecklist];
  abrir: [id: number];
}>();

const elementos = computed(() => props.actividad.checklist ?? []);
const puedeEditar = computed(() => props.pizarra.permisos.editar);
const puedeCrear = computed(() => props.pizarra.permisos.crear && !props.sinConvertir);
const hechos = computed(() => elementos.value.filter((e) => e.hecho).length);
const completa = computed(() => elementos.value.length > 0 && hechos.value === elementos.value.length);

const nuevo = ref("");
const error = ref("");
const ocupado = ref(false);
const hayConvertidos = computed(() => elementos.value.some((e) => e.actividad));
/** Las listas que se pueden elegir: todas menos la de esta actividad (sus hijas nacen ahí), salvo
 * que ya fuera la elegida (la actividad se movió a ella después). */
const opcionesTerminado = computed(() =>
  props.pizarra.listas.filter((l) => l.id !== props.actividad.lista || l.id === props.actividad.lista_terminado),
);
/** «Al completar, mover a»: sin la lista donde ya está (no la movería), salvo que ya fuera la elegida. */
const opcionesAlCompletar = computed(() =>
  props.pizarra.listas.filter((l) => l.id !== props.actividad.lista || l.id === props.actividad.lista_al_completar),
);

const vEnfocar = { mounted: (el: HTMLElement) => el.focus() };
const editando = ref<number | null>(null);
const textoEditado = ref("");

async function enviar(ruta: string, metodo: "POST" | "PATCH" | "DELETE", datos?: unknown) {
  ocupado.value = true;
  try {
    const t = await api<Actividad>(ruta, metodo, datos);
    emit("actualizada", t);
    return t;
  } catch (e) {
    error.value =
      e instanceof ErrorApi
        ? (e.campos.texto ?? e.campos.lista_terminado ?? e.campos.lista_al_completar ?? e.message)
        : mensajeDeError(e);
    return null;
  } finally {
    ocupado.value = false;
  }
}

async function agregar() {
  error.value = "";
  const texto = nuevo.value.trim();
  if (!texto) return;
  if (await enviar(`actividades/${props.actividad.id}/checklist/`, "POST", { texto })) nuevo.value = "";
}

/** Completar la checklist pudo moverla («Mover a … al completar»). */
function avisarSiSeMovio(antes: number, t: Actividad | null) {
  if (t && t.lista !== antes) avisar(`Se completó la checklist y se movió a «${t.lista_nombre}».`);
}

async function palomear(e: ElementoChecklist) {
  const antes = props.actividad.lista;
  avisarSiSeMovio(antes, await enviar(`checklist/${e.id}/`, "PATCH", { hecho: !e.hecho }));
}

function empezarEdicion(e: ElementoChecklist) {
  if (!puedeEditar.value || ocupado.value) return;
  editando.value = e.id;
  textoEditado.value = e.texto;
}

async function guardarTexto(e: ElementoChecklist) {
  if (editando.value !== e.id) return;
  const texto = textoEditado.value.trim();
  editando.value = null;
  if (!texto || texto === e.texto) return;
  error.value = "";
  await enviar(`checklist/${e.id}/`, "PATCH", { texto });
}

async function copiar() {
  try {
    await copiarTexto(textoChecklist(elementos.value));
    avisar("Se copió la checklist.");
  } catch {
    avisar("No se pudo copiar la checklist.");
  }
}

async function cambiarAlCompletar(ev: Event) {
  error.value = "";
  const select = ev.target as HTMLSelectElement;
  const lista = select.value ? Number(select.value) : null;
  if (await enviar(`actividades/${props.actividad.id}/`, "PATCH", { lista_al_completar: lista })) {
    const nombre = props.pizarra.listas.find((l) => l.id === lista)?.nombre;
    avisar(nombre ? `Al completar la checklist se moverá a «${nombre}».` : "Completar la checklist ya no la mueve.");
  } else select.value = String(props.actividad.lista_al_completar ?? "");
}
async function quitar(e: ElementoChecklist) {
  const antes = props.actividad.lista;
  avisarSiSeMovio(antes, await enviar(`checklist/${e.id}/`, "DELETE"));
}

function alSoltar({ id, antesDe }: Soltado) {
  const ids = elementos.value.map((e) => e.id).filter((x) => x !== id);
  const i = antesDe === null ? ids.length : ids.indexOf(antesDe);
  ids.splice(i < 0 ? ids.length : i, 0, id);
  enviar(`actividades/${props.actividad.id}/checklist/orden/`, "POST", { ids });
}

async function cambiarTerminado(ev: Event) {
  error.value = "";
  const select = ev.target as HTMLSelectElement;
  const lista = select.value ? Number(select.value) : null;
  if (await enviar(`actividades/${props.actividad.id}/`, "PATCH", { lista_terminado: lista })) {
    const nombre = props.pizarra.listas.find((l) => l.id === lista)?.nombre;
    avisar(nombre ? `Se marcó «${nombre}» como la lista de terminado.` : "Se pasó la checklist a palomeo manual.");
  } else select.value = String(props.actividad.lista_terminado ?? "");
}
</script>

<template>
  <div class="campo">
    <div class="checklist-cab">
      <span class="etiqueta">Checklist<template v-if="elementos.length"> · {{ hechos }}/{{ elementos.length }}</template></span>
      <button
        v-if="elementos.length"
        type="button"
        class="btn-icono"
        aria-label="Copiar la checklist como texto"
        title="Copiar como texto"
        @click="copiar"
      >
        <Icono nombre="copiar" />
      </button>
      <label v-if="elementos.length && (puedeEditar || actividad.lista_al_completar)" class="al-completar">
        Al completar, mover a
        <select :value="actividad.lista_al_completar ?? ''" :disabled="!puedeEditar || ocupado" @change="cambiarAlCompletar">
          <option value="">ninguna</option>
          <option v-for="l in opcionesAlCompletar" :key="l.id" :value="l.id">{{ l.nombre }}</option>
        </select>
      </label>
    </div>
    <div v-if="elementos.length" class="avance" :class="{ completo: completa }">
      <i :style="{ width: `${(hechos / elementos.length) * 100}%` }" />
    </div>
    <ul
      v-arrastrable="{ grupo: `checklist-${actividad.id}`, alSoltar, activo: puedeEditar, manija: '.manija' }"
      class="checklist"
    >
      <li v-for="e in elementos" :key="e.id" :data-id="e.id" :class="{ hecho: e.hecho }">
        <span v-if="puedeEditar && elementos.length > 1" class="manija" aria-hidden="true"><Icono nombre="arrastrar" /></span>
        <template v-if="e.actividad">
          <span v-if="e.automatico" class="caja-enlace" :aria-label="e.hecho ? 'Hecho' : 'Pendiente'"
            ><Icono v-if="e.hecho" nombre="palomita"
          /></span>
          <input
            v-else
            type="checkbox"
            :checked="e.hecho"
            :disabled="!puedeEditar || ocupado"
            :aria-label="e.texto"
            @change="palomear(e)"
          />
          <button type="button" class="enlace-actividad" @click="emit('abrir', e.actividad.id)">
            <span class="texto">{{ e.texto }}</span>
            <small><Icono nombre="enlace" /> En «{{ e.actividad.lista_nombre }}»</small>
          </button>
        </template>
        <template v-else>
          <div class="elemento">
            <input
              type="checkbox"
              :checked="e.hecho"
              :disabled="!puedeEditar || ocupado"
              :aria-label="e.texto"
              @change="palomear(e)"
            />
            <textarea
              v-if="editando === e.id"
              v-model="textoEditado"
              v-enfocar
              class="editar-texto"
              rows="2"
              :maxlength="MAX_TEXTO_ELEMENTO"
              aria-label="Texto del elemento"
              @keydown.enter.prevent="guardarTexto(e)"
              @keydown.esc.stop.prevent="editando = null"
              @blur="guardarTexto(e)"
            />
            <span
              v-else-if="puedeEditar"
              class="texto editable"
              role="button"
              tabindex="0"
              :title="`Editar «${e.texto}»`"
              @click="empezarEdicion(e)"
              @keydown.enter.prevent="empezarEdicion(e)"
              >{{ e.texto }}</span
            >
            <span v-else class="texto">{{ e.texto }}</span>
          </div>
          <button
            type="button"
            v-if="puedeCrear"
            class="btn-icono"
            :aria-label="`Convertir «${e.texto}» en actividad`"
            title="Convertir en actividad"
            @click="emit('convertir', e)"
          >
            <Icono nombre="enlace" />
          </button>
        </template>
        <button
          type="button"
          v-if="puedeEditar"
          class="btn-icono"
          :aria-label="`Quitar «${e.texto}»`"
          title="Quitar"
          :disabled="ocupado"
          @click="quitar(e)"
        >
          <Icono nombre="cerrarChico" />
        </button>
      </li>
    </ul>
    <div v-if="hayConvertidos" class="lista-terminado">
      <Icono nombre="palomitaCirculo" />
      <label for="lista-terminado">Lo que llega a</label>
      <select
        id="lista-terminado"
        :value="actividad.lista_terminado ?? ''"
        :disabled="!puedeEditar || ocupado"
        @change="cambiarTerminado"
      >
        <option value="">ninguna (a mano)</option>
        <option v-for="l in opcionesTerminado" :key="l.id" :value="l.id">{{ l.nombre }}</option>
      </select>
      <span>cuenta como terminado</span>
    </div>
    <div v-if="puedeEditar" class="agregar-item">
      <input
        v-model="nuevo"
        type="text"
        :maxlength="MAX_TEXTO_ELEMENTO"
        placeholder="Agregar elemento"
        aria-label="Agregar elemento a la checklist"
        @keydown.enter.prevent="agregar"
      />
      <button type="button" class="btn btn-chico btn-secundario" :disabled="ocupado || !nuevo.trim()" @click="agregar">
        Agregar
      </button>
    </div>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="!elementos.length && !puedeEditar" class="ayuda">Sin checklist.</div>
  </div>
</template>
