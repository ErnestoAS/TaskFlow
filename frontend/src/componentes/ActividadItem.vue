<!--
  Actividad en el tablero o en «Mis actividades» (`enMis`: con pizarra y lista, sin descripción).
-->
<script setup lang="ts">
import { computed } from "vue";

import type { Actividad, Tipo } from "../tipos";
import Avatares from "./Avatares.vue";
import Chips from "./Chips.vue";
import Icono from "./Icono.vue";

const props = defineProps<{ actividad: Actividad; tipos?: Tipo[]; enMis?: boolean }>();
defineEmits<{ abrir: [id: number] }>();

const susTipos = computed(() => (props.tipos ?? []).filter((tp) => props.actividad.tipos.includes(tp.id)));
const checklist = computed(() => props.actividad.checklist_conteo);
</script>

<template>
  <button
    class="actividad"
    :data-id="actividad.id"
    @click="$emit('abrir', actividad.id)"
  >
    <span v-if="enMis" class="pizarra-de">{{ actividad.pizarra_nombre }}</span>
    <h4>{{ actividad.titulo }}</h4>
    <p v-if="!enMis && actividad.descripcion">{{ actividad.descripcion }}</p>
    <div v-if="enMis || susTipos.length" class="etiquetas">
      <Chips v-if="enMis" :lista="actividad.lista_nombre" />
      <Chips v-for="tp in susTipos" :key="tp.id" :tipo="tp" />
    </div>
    <div class="pie">
      <Chips :fecha="actividad" />
      <span
        v-if="checklist"
        class="chip avance-checklist"
        :class="{ completo: checklist.hechos === checklist.total }"
        :title="`Checklist: ${checklist.hechos} de ${checklist.total}`"
        ><Icono nombre="checklist" /> {{ checklist.hechos }}/{{ checklist.total }}</span
      >
      <span v-if="actividad.n_adjuntos" class="chip avance-checklist" :title="`${actividad.n_adjuntos} adjuntos`"
        ><Icono nombre="clip" /> {{ actividad.n_adjuntos }}</span
      >
      <Avatares v-if="actividad.asignados.length" :usuarios="actividad.asignados" />
      <span v-else class="chip fecha" style="margin-left: auto">Sin asignar</span>
    </div>
  </button>
</template>
