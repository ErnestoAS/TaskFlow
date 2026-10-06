<!--
  Checklist del detalle de una tarjeta (§4.6). Palomear, agregar, ordenar (arrastrando la manija) y
  quitar: permiso «Editar». Convertir un elemento en tarjeta enlazada: permiso «Crear» (lo hace
  PanelTarjeta con el formulario). Un elemento convertido muestra en qué lista está su tarjeta.
  Si hay alguno, debajo va «Lo que llega a [lista] cuenta como terminado» (2026-10-06): una lista
  para toda la checklist, distinta de la de esta tarjeta; con ella, los convertidos se palomean
  solos. «Ninguna» = a mano.
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { vArrastrable, type Soltado } from "../arrastre";
import type { ElementoChecklist, PizarraDetalle, Tarjeta } from "../tipos";
import { avisar } from "../ui";
import Icono from "./Icono.vue";

const props = defineProps<{ tarjeta: Tarjeta; pizarra: PizarraDetalle }>();
const emit = defineEmits<{
  actualizada: [t: Tarjeta];
  convertir: [e: ElementoChecklist];
  abrir: [id: number];
}>();

const elementos = computed(() => props.tarjeta.checklist ?? []);
const puedeEditar = computed(() => props.pizarra.permisos.editar);
const puedeCrear = computed(() => props.pizarra.permisos.crear);
const hechos = computed(() => elementos.value.filter((e) => e.hecho).length);
const completa = computed(() => elementos.value.length > 0 && hechos.value === elementos.value.length);

const nuevo = ref("");
const error = ref("");
const ocupado = ref(false);
const hayConvertidos = computed(() => elementos.value.some((e) => e.tarjeta));
/** Las listas que se pueden elegir: todas menos la de esta tarjeta (sus hijas nacen ahí), salvo
 * que ya fuera la elegida (la tarjeta se movió a ella después). */
const opcionesTerminado = computed(() =>
  props.pizarra.listas.filter((l) => l.id !== props.tarjeta.lista || l.id === props.tarjeta.lista_terminado),
);

async function enviar(ruta: string, metodo: "POST" | "PATCH" | "DELETE", datos?: unknown) {
  ocupado.value = true;
  try {
    emit("actualizada", await api<Tarjeta>(ruta, metodo, datos));
    return true;
  } catch (e) {
    error.value =
      e instanceof ErrorApi ? (e.campos.texto ?? e.campos.lista_terminado ?? e.message) : mensajeDeError(e);
    return false;
  } finally {
    ocupado.value = false;
  }
}

async function agregar() {
  error.value = "";
  const texto = nuevo.value.trim();
  if (!texto) return;
  if (await enviar(`tarjetas/${props.tarjeta.id}/checklist/`, "POST", { texto })) nuevo.value = "";
}

const palomear = (e: ElementoChecklist) => enviar(`checklist/${e.id}/`, "PATCH", { hecho: !e.hecho });
const quitar = (e: ElementoChecklist) => enviar(`checklist/${e.id}/`, "DELETE");

function alSoltar({ id, antesDe }: Soltado) {
  const ids = elementos.value.map((e) => e.id).filter((x) => x !== id);
  const i = antesDe === null ? ids.length : ids.indexOf(antesDe);
  ids.splice(i < 0 ? ids.length : i, 0, id);
  enviar(`tarjetas/${props.tarjeta.id}/checklist/orden/`, "POST", { ids });
}

async function cambiarTerminado(ev: Event) {
  error.value = "";
  const select = ev.target as HTMLSelectElement;
  const lista = select.value ? Number(select.value) : null;
  if (await enviar(`tarjetas/${props.tarjeta.id}/`, "PATCH", { lista_terminado: lista })) {
    const nombre = props.pizarra.listas.find((l) => l.id === lista)?.nombre;
    avisar(nombre ? `Se marcó «${nombre}» como la lista de terminado.` : "Se pasó la checklist a palomeo manual.");
  } else select.value = String(props.tarjeta.lista_terminado ?? "");
}
</script>

<template>
  <div class="campo">
    <span class="etiqueta">Checklist<template v-if="elementos.length"> · {{ hechos }}/{{ elementos.length }}</template></span>
    <div v-if="elementos.length" class="avance" :class="{ completo: completa }">
      <i :style="{ width: `${(hechos / elementos.length) * 100}%` }" />
    </div>
    <ul
      v-arrastrable="{ grupo: `checklist-${tarjeta.id}`, alSoltar, activo: puedeEditar, manija: '.manija' }"
      class="checklist"
    >
      <li v-for="e in elementos" :key="e.id" :data-id="e.id" :class="{ hecho: e.hecho }">
        <span v-if="puedeEditar && elementos.length > 1" class="manija" aria-hidden="true"><Icono nombre="arrastrar" /></span>
        <template v-if="e.tarjeta">
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
          <button class="enlace-tarjeta" @click="emit('abrir', e.tarjeta.id)">
            <span class="texto">{{ e.texto }}</span>
            <small><Icono nombre="enlace" /> En «{{ e.tarjeta.lista_nombre }}»</small>
          </button>
        </template>
        <template v-else>
          <label>
            <input type="checkbox" :checked="e.hecho" :disabled="!puedeEditar || ocupado" @change="palomear(e)" />
            <span class="texto">{{ e.texto }}</span>
          </label>
          <button
            v-if="puedeCrear"
            class="btn-icono"
            :aria-label="`Convertir «${e.texto}» en tarjeta`"
            title="Convertir en tarjeta"
            @click="emit('convertir', e)"
          >
            <Icono nombre="enlace" />
          </button>
        </template>
        <button
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
        :value="tarjeta.lista_terminado ?? ''"
        :disabled="!puedeEditar || ocupado"
        @change="cambiarTerminado"
      >
        <option value="">ninguna (a mano)</option>
        <option v-for="l in opcionesTerminado" :key="l.id" :value="l.id">{{ l.nombre }}</option>
      </select>
      <span>cuenta como terminado</span>
    </div>
    <form v-if="puedeEditar" class="agregar-item" novalidate @submit.prevent="agregar">
      <input v-model="nuevo" type="text" maxlength="200" placeholder="Agregar elemento" aria-label="Agregar elemento a la checklist" />
      <button type="submit" class="btn btn-chico btn-secundario" :disabled="ocupado || !nuevo.trim()">Agregar</button>
    </form>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-if="elementos.length && puedeCrear" class="ayuda">
      Con <Icono nombre="enlace" /> conviertes un elemento en tarjeta enlazada; se palomea solo cuando esa tarjeta llega
      a la lista que elijas en «Lo que llega a … cuenta como terminado».
    </div>
    <div v-else-if="!elementos.length && !puedeEditar" class="ayuda">Sin checklist.</div>
  </div>
</template>
