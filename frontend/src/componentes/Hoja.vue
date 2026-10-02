<!-- Hoja inferior (teléfono) o panel lateral (computadora). Se cierra con Escape o tocando el velo. -->
<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";

import Icono from "./Icono.vue";

defineProps<{ titulo: string }>();
const emit = defineEmits<{ cerrar: [] }>();
const hoja = ref<HTMLElement>();

function tecla(e: KeyboardEvent) {
  if (e.key === "Escape") emit("cerrar");
}
onMounted(async () => {
  document.addEventListener("keydown", tecla);
  document.body.style.overflow = "hidden";
  await nextTick();
  hoja.value?.querySelector<HTMLElement>("input,textarea,button:not(.btn-icono)")?.focus({ preventScroll: true });
});
onBeforeUnmount(() => {
  document.removeEventListener("keydown", tecla);
  document.body.style.overflow = "";
});
</script>

<template>
  <div class="velo" @click.self="emit('cerrar')">
    <div ref="hoja" class="hoja" role="dialog" aria-modal="true" :aria-label="titulo">
      <div class="asa" />
      <div class="hoja-cab">
        <h2>{{ titulo }}</h2>
        <button class="btn-icono" aria-label="Cerrar" @click="emit('cerrar')"><Icono nombre="cerrar" /></button>
      </div>
      <slot />
    </div>
  </div>
</template>
