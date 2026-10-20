<!-- Caja de búsqueda de actividades (2026-10-20): la lupa, el texto y una ✕ para borrarlo (también Escape). -->
<script setup lang="ts">
import Icono from "./Icono.vue";

const texto = defineModel<string>({ required: true });
</script>

<template>
  <div class="buscador" role="search">
    <Icono nombre="lupa" />
    <input
      v-model="texto"
      type="search"
      maxlength="100"
      placeholder="Buscar en título o descripción"
      aria-label="Buscar actividades por título o descripción"
      @keydown.esc="texto = ''"
    />
    <button v-if="texto" type="button" class="btn-icono" aria-label="Borrar búsqueda" @click="texto = ''">
      <Icono nombre="cerrarChico" />
    </button>
  </div>
</template>
