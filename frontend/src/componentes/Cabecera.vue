<!-- Cabecera blanca. Con `atras` muestra el botón de regresar; sin él, el símbolo (solo teléfono). -->
<script setup lang="ts">
import type { RouteLocationRaw } from "vue-router";

import Icono from "./Icono.vue";
import Logo from "./Logo.vue";

defineProps<{ titulo: string; sub?: string; atras?: RouteLocationRaw }>();
</script>

<template>
  <header class="cabecera">
    <RouterLink v-if="atras" :to="atras" class="btn-icono" aria-label="Regresar"><Icono nombre="atras" /></RouterLink>
    <span v-else class="sello"><Logo /></span>
    <div class="titulos">
      <h1>{{ titulo }}</h1>
      <div v-if="sub" class="sub">{{ sub }}</div>
    </div>
    <div class="acciones-cab"><slot name="acciones" /></div>
    <slot name="telefono" />
  </header>
</template>
