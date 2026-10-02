<!--
  Invita a instalar la PWA. Chrome/Edge/Android: botón que abre el diálogo del navegador
  (beforeinstallprompt). iOS: pasos de Safari, porque ahí no hay diálogo. Si ya está instalada o
  el usuario lo descartó, no aparece (salvo que llegue de la portada con ?instalar=1).
-->
<script setup lang="ts">
import { computed } from "vue";

import { descartar, instalacion, instalar } from "../instalacion";
import Icono from "./Icono.vue";

const visible = computed(
  () =>
    !instalacion.instalada &&
    (instalacion.evento || instalacion.esIOS) &&
    (!instalacion.descartada || instalacion.pedida),
);
</script>

<template>
  <div v-if="visible" class="franja" role="region" aria-label="Instalar TaskFlow">
    <Icono nombre="descargar" />
    <span v-if="instalacion.evento">Instala TaskFlow para abrirlo desde tu pantalla de inicio, como cualquier app.</span>
    <span v-else>
      Para instalar TaskFlow en tu iPhone o iPad:
      <ol class="pasos-ios">
        <li>Toca <b>Compartir</b> <Icono nombre="compartir" :tam="14" /> en la barra de Safari.</li>
        <li>Elige <b>Agregar a pantalla de inicio</b>.</li>
        <li>Toca <b>Agregar</b>.</li>
      </ol>
    </span>
    <button v-if="instalacion.evento" class="btn btn-chico btn-primario" @click="instalar">Instalar</button>
    <button class="btn-icono" aria-label="No mostrar de nuevo" @click="descartar"><Icono nombre="cerrar" :tam="18" /></button>
  </div>
</template>
