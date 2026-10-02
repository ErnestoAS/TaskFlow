<!-- Avatares en escala navy/pizarra (--av1…--av6), color estable por usuario. -->
<script setup lang="ts">
import { computed } from "vue";

import type { Usuario } from "../tipos";

const props = withDefaults(defineProps<{ usuarios: Usuario[]; max?: number }>(), { max: 3 });
const visibles = computed(() => props.usuarios.slice(0, props.max));
const extra = computed(() => props.usuarios.length - props.max);
</script>

<template>
  <span class="avatares">
    <span
      v-for="u in visibles"
      :key="u.id"
      class="avatar"
      :style="{ background: `var(--av${(u.id % 6) + 1})` }"
      :title="u.nombre"
      >{{ u.iniciales }}</span
    >
    <span v-if="extra > 0" class="avatar mas">+{{ extra }}</span>
  </span>
</template>
