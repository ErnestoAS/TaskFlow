<!-- Chips de lista, prioridad, fecha y tipo: punto de color, texto -text, fondo -soft. -->
<script setup lang="ts">
import { computed } from "vue";

import type { Prioridad, Tarjeta, Tipo } from "../tipos";
import { estadoFecha, nombrePrioridad } from "../utilidades";
import Icono from "./Icono.vue";

const props = defineProps<{
  /** Nombre de una lista: neutro, las listas no tienen color (§4.6). */
  lista?: string;
  prioridad?: Prioridad;
  fecha?: Pick<Tarjeta, "fecha_fin" | "en_cierre">;
  tipo?: Tipo;
}>();
const fecha = computed(() => (props.fecha ? estadoFecha(props.fecha) : null));
</script>

<template>
  <span v-if="lista !== undefined" class="chip nombre-lista">{{ lista }}</span>
  <span v-else-if="prioridad" class="chip" :class="`prio-${prioridad}`"
    ><span class="punto" />{{ nombrePrioridad(prioridad) }}</span
  >
  <span v-else-if="fecha" class="chip" :class="fecha.clase"
    ><Icono :nombre="fecha.clase === 'vencida' ? 'alerta' : 'calendario'" />{{ fecha.texto }}</span
  >
  <span v-else-if="tipo" class="chip tipo" :style="{ '--tipo': tipo.color }" :title="tipo.descripcion || undefined"
    ><span class="punto" />{{ tipo.nombre }}</span
  >
</template>
