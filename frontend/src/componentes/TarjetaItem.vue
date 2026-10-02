<script setup lang="ts">
import { computed } from "vue";

import type { Tarjeta, Tipo } from "../tipos";
import Avatares from "./Avatares.vue";
import Chips from "./Chips.vue";

const props = defineProps<{ tarjeta: Tarjeta; tipos?: Tipo[]; conProyecto?: boolean }>();
defineEmits<{ abrir: [id: number] }>();

const terminada = computed(() => props.tarjeta.estatus === "finalizada");
const susTipos = computed(() => (props.tipos ?? []).filter((tp) => props.tarjeta.tipos.includes(tp.id)));
</script>

<template>
  <button
    class="tarjeta"
    :class="{ urgente: tarjeta.prioridad === 'urgente' && !terminada, terminada }"
    @click="$emit('abrir', tarjeta.id)"
  >
    <span v-if="conProyecto" class="proyecto-de">{{ tarjeta.proyecto_nombre }}</span>
    <h4>{{ tarjeta.titulo }}</h4>
    <p v-if="tarjeta.descripcion">{{ tarjeta.descripcion }}</p>
    <div v-if="susTipos.length || !terminada" class="etiquetas">
      <Chips v-for="tp in susTipos" :key="tp.id" :tipo="tp" />
      <Chips v-if="!terminada" :prioridad="tarjeta.prioridad" />
    </div>
    <div class="pie">
      <Chips v-if="conProyecto" :estatus="tarjeta.estatus" />
      <Chips :fecha="tarjeta" />
      <Avatares v-if="tarjeta.asignados.length" :usuarios="tarjeta.asignados" />
      <span v-else class="chip fecha" style="margin-left: auto">Sin asignar</span>
    </div>
  </button>
</template>
