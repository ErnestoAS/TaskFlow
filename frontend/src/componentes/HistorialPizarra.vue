<!--
  Historial de la pizarra (2026-10-20, §5): quién creó, movió, eliminó o comentó qué, más reciente
  arriba y agrupado por día; filtro por persona y «Ver más» (50 por vez). Tocar una entrada abre su
  actividad; las eliminadas van sin enlace. Para el caso «alguien movió algo y no lo encuentro».
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { api, mensajeDeError } from "../api";
import { sesion } from "../sesion";
import type { EntradaHistorial, PizarraDetalle } from "../tipos";
import Chips from "./Chips.vue";
import Hoja from "./Hoja.vue";

const props = defineProps<{ pizarra: PizarraDetalle }>();
const emit = defineEmits<{ cerrar: []; abrir: [id: number] }>();

const entradas = ref<EntradaHistorial[]>([]);
const mas = ref(false);
const cargando = ref(false);
const error = ref("");
/** Id de usuario como texto; vacío = todas las personas. */
const persona = ref("");

async function cargar(siguiente = false) {
  cargando.value = true;
  error.value = "";
  const params = new URLSearchParams();
  if (persona.value) params.set("persona", persona.value);
  if (siguiente && entradas.value.length) params.set("antes", entradas.value[entradas.value.length - 1].fecha);
  const consulta = params.toString();
  try {
    const r = await api<{ entradas: EntradaHistorial[]; mas: boolean }>(
      `pizarras/${props.pizarra.id}/historial/${consulta ? `?${consulta}` : ""}`,
    );
    entradas.value = siguiente ? [...entradas.value, ...r.entradas] : r.entradas;
    mas.value = r.mas;
  } catch (e) {
    error.value = mensajeDeError(e, "No se pudo cargar el historial.");
  } finally {
    cargando.value = false;
  }
}
watch(persona, () => cargar(), { immediate: true });

const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
const MESES = [
  "enero", "febrero", "marzo", "abril", "mayo", "junio",
  "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
];

/** «Hoy», «Ayer» o «lunes 18 de octubre» (con el año si no es este). */
function dia(f: Date): string {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  const ese = new Date(f);
  ese.setHours(0, 0, 0, 0);
  const dias = Math.round((hoy.getTime() - ese.getTime()) / 864e5);
  if (dias === 0) return "Hoy";
  if (dias === 1) return "Ayer";
  const anio = f.getFullYear() === hoy.getFullYear() ? "" : ` de ${f.getFullYear()}`;
  return `${DIAS[f.getDay()]} ${f.getDate()} de ${MESES[f.getMonth()]}${anio}`;
}

const hora = (f: Date) => `${String(f.getHours()).padStart(2, "0")}:${String(f.getMinutes()).padStart(2, "0")}`;

const grupos = computed(() => {
  const salida: { dia: string; entradas: (EntradaHistorial & { hora: string })[] }[] = [];
  for (const e of entradas.value) {
    const f = new Date(e.fecha);
    const nombre = dia(f);
    if (salida[salida.length - 1]?.dia !== nombre) salida.push({ dia: nombre, entradas: [] });
    salida[salida.length - 1].entradas.push({ ...e, hora: hora(f) });
  }
  return salida;
});

const quien = (e: EntradaHistorial) =>
  `${e.usuario?.nombre ?? "Usuario eliminado"}${e.usuario?.id === sesion.usuario?.id ? " (tú)" : ""}`;
</script>

<template>
  <Hoja titulo="Historial de la pizarra" @cerrar="emit('cerrar')">
    <div class="campo">
      <label for="h-persona">Persona</label>
      <select id="h-persona" v-model="persona">
        <option value="">Todas las personas</option>
        <option v-for="m in pizarra.miembros" :key="m.usuario.id" :value="String(m.usuario.id)">
          {{ m.usuario.nombre }}{{ m.usuario.id === sesion.usuario?.id ? " (tú)" : "" }}
        </option>
      </select>
    </div>
    <div v-if="error" class="error-general" role="alert">{{ error }}</div>
    <div v-if="cargando && !entradas.length" class="cargando" style="min-height: 120px">Cargando…</div>
    <div v-else-if="!entradas.length && !error" class="vacio">Todavía no hay nada en el historial.</div>

    <template v-for="g in grupos" :key="g.dia">
      <div class="seccion-titulo">{{ g.dia }}</div>
      <ul class="historial-pizarra">
        <li v-for="(e, i) in g.entradas" :key="`${e.fecha}-${i}`">
          <component
            :is="e.actividad.id ? 'button' : 'div'"
            :type="e.actividad.id ? 'button' : undefined"
            class="entrada"
            @click="e.actividad.id && emit('abrir', e.actividad.id)"
          >
            <span class="que">
              <b>{{ quien(e) }}</b>
              <template v-if="e.tipo === 'comentario'"> comentó en <b>«{{ e.actividad.titulo }}»</b></template>
              <template v-else-if="e.nota">, en <b>«{{ e.actividad.titulo }}»</b>: {{ e.nota }}</template>
              <template v-else-if="e.de && e.a">
                movió <b>«{{ e.actividad.titulo }}»</b> de <Chips :lista="e.de" /> a <Chips :lista="e.a" />
              </template>
              <template v-else-if="e.de"> eliminó <b>«{{ e.actividad.titulo }}»</b> de <Chips :lista="e.de" /></template>
              <template v-else> creó <b>«{{ e.actividad.titulo }}»</b> en <Chips :lista="e.a ?? ''" /></template>
            </span>
            <span v-if="e.texto" class="cita">{{ e.texto }}</span>
            <span class="cuando">{{ e.hora }}</span>
          </component>
        </li>
      </ul>
    </template>

    <button v-if="mas" type="button" class="btn btn-secundario" style="width: 100%" :disabled="cargando" @click="cargar(true)">
      {{ cargando ? "Cargando…" : "Ver más" }}
    </button>
  </Hoja>
</template>
