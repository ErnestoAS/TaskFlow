<!--
  Tarjeta en el tablero o en «Mis tarjetas» (`enMis`: con pizarra y lista, sin descripción).
  La prioridad media no se muestra (es la de omisión). Urgente lleva el indicador lateral rojo.
-->
<script setup lang="ts">
import { computed } from "vue";

import type { Tarjeta, Tipo } from "../tipos";
import Avatares from "./Avatares.vue";
import Chips from "./Chips.vue";
import Icono from "./Icono.vue";

const props = defineProps<{ tarjeta: Tarjeta; tipos?: Tipo[]; enMis?: boolean }>();
defineEmits<{ abrir: [id: number] }>();

const susTipos = computed(() => (props.tipos ?? []).filter((tp) => props.tarjeta.tipos.includes(tp.id)));
const checklist = computed(() => props.tarjeta.checklist_conteo);
</script>

<template>
  <button
    class="tarjeta"
    :class="{ urgente: tarjeta.prioridad === 'urgente' }"
    :data-id="tarjeta.id"
    @click="$emit('abrir', tarjeta.id)"
  >
    <span v-if="enMis" class="pizarra-de">{{ tarjeta.pizarra_nombre }}</span>
    <h4>{{ tarjeta.titulo }}</h4>
    <p v-if="!enMis && tarjeta.descripcion">{{ tarjeta.descripcion }}</p>
    <div v-if="enMis || susTipos.length || tarjeta.prioridad !== 'media'" class="etiquetas">
      <Chips v-if="enMis" :lista="tarjeta.lista_nombre" />
      <Chips v-for="tp in susTipos" :key="tp.id" :tipo="tp" />
      <Chips v-if="tarjeta.prioridad !== 'media'" :prioridad="tarjeta.prioridad" />
    </div>
    <div class="pie">
      <Chips :fecha="tarjeta" />
      <span
        v-if="checklist"
        class="chip avance-checklist"
        :class="{ completo: checklist.hechos === checklist.total }"
        :title="`Checklist: ${checklist.hechos} de ${checklist.total}`"
        ><Icono nombre="checklist" /> {{ checklist.hechos }}/{{ checklist.total }}</span
      >
      <Avatares v-if="tarjeta.asignados.length" :usuarios="tarjeta.asignados" />
      <span v-else class="chip fecha" style="margin-left: auto">Sin asignar</span>
    </div>
  </button>
</template>
