<!-- Chips de estatus, prioridad, fecha y tipo: punto de color, texto -text, fondo -soft. -->
<script setup lang="ts">
import { computed } from "vue";

import type { Estatus, Prioridad, Tarjeta, Tipo } from "../tipos";
import { estadoFecha, nombreEstatus, nombrePrioridad } from "../utilidades";
import Icono from "./Icono.vue";

const props = defineProps<{
  estatus?: Estatus;
  prioridad?: Prioridad;
  fecha?: Pick<Tarjeta, "fecha_fin" | "estatus">;
  tipo?: Tipo;
}>();
const fecha = computed(() => (props.fecha ? estadoFecha(props.fecha) : null));
</script>

<template>
  <span v-if="estatus" class="chip" :class="estatus"><span class="punto" />{{ nombreEstatus(estatus) }}</span>
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
