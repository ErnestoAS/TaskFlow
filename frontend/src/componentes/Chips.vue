<!-- Chips de lista, fecha y tipo: punto de color, texto -text, fondo -soft. -->
<script setup lang="ts">
import { computed } from "vue";

import type { Actividad, Tipo } from "../tipos";
import { estadoFecha } from "../utilidades";
import Icono from "./Icono.vue";

const props = defineProps<{
  /** Nombre de una lista: neutro, las listas no tienen color (§4.6). */
  lista?: string;
  fecha?: Pick<Actividad, "fecha_fin">;
  tipo?: Tipo;
}>();
const fecha = computed(() => (props.fecha ? estadoFecha(props.fecha) : null));
</script>

<template>
  <span v-if="lista !== undefined" class="chip nombre-lista">{{ lista }}</span>
  <span v-else-if="fecha" class="chip" :class="fecha.clase"
    ><Icono :nombre="fecha.clase === 'vencida' ? 'alerta' : 'calendario'" />{{ fecha.texto }}</span
  >
  <span v-else-if="tipo" class="chip tipo" :style="{ '--tipo': tipo.color }" :title="tipo.descripcion || undefined"
    ><span class="punto" />{{ tipo.nombre }}</span
  >
</template>
