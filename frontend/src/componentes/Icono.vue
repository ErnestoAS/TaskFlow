<!-- Íconos de trazo de la maqueta app-v2. Uno solo por nombre; tamaño y grosor según el uso. -->
<script setup lang="ts">
import { computed } from "vue";

const ICONOS = {
  carpetas: [22, 1.8, '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>'],
  check: [22, 1.8, '<rect x="3" y="4" width="18" height="16" rx="3"/><path d="m8 12 3 3 5-6"/>'],
  persona: [22, 1.8, '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>'],
  personas: [20, 1.8, '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8"/><path d="M18.5 20a6.5 6.5 0 0 0-3-5.5"/>'],
  atras: [22, 2, '<path d="m15 18-6-6 6-6"/>'],
  mas: [26, 2.2, '<path d="M12 5v14M5 12h14"/>'],
  masChico: [16, 2.4, '<path d="M12 5v14M5 12h14"/>'],
  cerrar: [22, 2, '<path d="M18 6 6 18M6 6l12 12"/>'],
  calendario: [13, 2, '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>'],
  alerta: [13, 2.2, '<path d="M12 9v4M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/>'],
  correo: [16, 1.8, '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>'],
  palomita: [12, 3, '<path d="m5 12 5 5 9-10"/>'],
  archivo: [18, 1.8, '<rect x="3" y="4" width="18" height="4" rx="1"/><path d="M5 8v11a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8M10 12h4"/>'],
  info: [18, 1.8, '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>'],
  descargar: [18, 1.8, '<path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/>'],
  compartir: [18, 1.8, '<path d="M12 15V3m0 0L8 7m4-4 4 4"/><path d="M6 11H5a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-8a1 1 0 0 0-1-1h-1"/>'],
  // v3 (2026-10-05): listas, checklist y filtros.
  checklist: [13, 2.2, '<rect x="3" y="3" width="18" height="18" rx="4"/><path d="m8 12 3 3 5-6"/>'],
  palomitaCirculo: [15, 2.2, '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>'],
  enlace: [15, 2, '<path d="M7 17 17 7M8 7h9v9"/>'],
  bandera: [15, 2, '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>'],
  puntos: [18, 2.6, '<path d="M5 12h.01M12 12h.01M19 12h.01"/>'],
  filtro: [15, 2, '<path d="M4 6h16M7 12h10M10 18h4"/>'],
  izquierda: [16, 2, '<path d="m15 18-6-6 6-6"/>'],
  derecha: [16, 2, '<path d="m9 18 6-6-6-6"/>'],
  cerrarChico: [15, 2, '<path d="M18 6 6 18M6 6l12 12"/>'],
  arrastrar: [14, 2, '<path d="M9 5h.01M9 12h.01M9 19h.01M15 5h.01M15 12h.01M15 19h.01"/>'],
  // 2026-10-06: acciones arriba del detalle de tarjeta.
  lapiz: [15, 2, '<path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16z"/><path d="m13.5 6.5 4 4"/>'],
  basura: [15, 2, '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>'],
  ajustes: [20, 1.8, '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/>'],
} as const;

export type NombreIcono = keyof typeof ICONOS;

const props = defineProps<{ nombre: NombreIcono; tam?: number }>();
const datos = computed(() => ICONOS[props.nombre]);
</script>

<template>
  <svg
    :width="tam ?? datos[0]"
    :height="tam ?? datos[0]"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    :stroke-width="datos[1]"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
    v-html="datos[2]"
  />
</template>
