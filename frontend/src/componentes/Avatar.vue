<script setup lang="ts">
import type { Usuario } from "../tipos";

defineProps<{ usuario: Usuario }>();
</script>

<template>
  <span class="avatar grande" :style="{ background: `var(--av${(usuario.id % 6) + 1})` }" aria-hidden="true">{{
    usuario.iniciales
  }}</span>
</template>
