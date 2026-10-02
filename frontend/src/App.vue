<!--
  Armazón: barra lateral navy (computadora), navegación inferior (teléfono), avisos breves,
  confirmaciones y el aviso de versión nueva del service worker. Las pantallas de acceso
  (entrar, registro, invitación) van sin armazón.
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { registerSW } from "virtual:pwa-register";

import Icono, { type NombreIcono } from "./componentes/Icono.vue";
import Logo from "./componentes/Logo.vue";
import { misProyectos, recargarProyectos } from "./proyectos";
import { sesion } from "./sesion";
import { ui } from "./ui";

const route = useRoute();
const router = useRouter();

const conArmazon = computed(() => !route.meta.publica && !!sesion.usuario);

const SECCIONES: [string, string, NombreIcono][] = [
  ["proyectos", "Proyectos", "carpetas"],
  ["mis-tarjetas", "Mis tarjetas", "check"],
  ["perfil", "Perfil", "persona"],
];
const enProyecto = computed(() => route.name === "tablero" || route.name === "ajustes");
const proyectoActual = computed(() => (enProyecto.value ? Number(route.params.id) : null));
const seccionActiva = computed(() => (enProyecto.value ? "proyectos" : String(route.name)));
const activos = computed(() => misProyectos.lista.filter((p) => !p.archivado));

// La barra lateral necesita la lista de proyectos en cualquier pantalla.
watch(
  conArmazon,
  (si) => {
    if (si && !misProyectos.cargados) recargarProyectos().catch(() => undefined);
  },
  { immediate: true },
);

// Versión nueva publicada: se avisa y se recarga cuando el usuario quiera (registerType "prompt").
const hayVersion = ref(false);
let actualizar: ((recargar?: boolean) => Promise<void>) | undefined;
if (import.meta.env.PROD) {
  actualizar = registerSW({ onNeedRefresh: () => (hayVersion.value = true) });
}
</script>

<template>
  <div v-if="!conArmazon"><RouterView /></div>
  <div v-else class="armazon">
    <nav class="nav-lateral" aria-label="Principal">
      <div class="marca-lateral"><Logo /><span>TaskFlow</span></div>
      <button
        v-for="[nombre, texto, icono] in SECCIONES"
        :key="nombre"
        :aria-current="!enProyecto && seccionActiva === nombre ? 'page' : undefined"
        @click="router.push({ name: nombre })"
      >
        <Icono :nombre="icono" /><span>{{ texto }}</span>
      </button>
      <template v-if="activos.length">
        <div class="separador" />
        <div class="rotulo-nav">Mis proyectos</div>
        <button
          v-for="p in activos"
          :key="p.id"
          :aria-current="proyectoActual === p.id ? 'page' : undefined"
          @click="router.push({ name: 'tablero', params: { id: p.id } })"
        >
          <svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true"><circle cx="4" cy="4" r="3" fill="currentColor" opacity=".6" /></svg>
          <span>{{ p.nombre }}</span>
        </button>
      </template>
    </nav>

    <div class="cuerpo">
      <RouterView />
    </div>

    <nav class="nav-inferior" aria-label="Principal">
      <button
        v-for="[nombre, texto, icono] in SECCIONES"
        :key="nombre"
        :aria-current="seccionActiva === nombre ? 'page' : undefined"
        @click="router.push({ name: nombre })"
      >
        <Icono :nombre="icono" /><span>{{ texto }}</span>
      </button>
    </nav>
  </div>

  <div v-if="hayVersion" class="toast" role="status" style="display: flex; gap: 12px; align-items: center">
    Hay una versión nueva de TaskFlow.
    <button class="btn btn-chico btn-primario" @click="actualizar?.(true)">Actualizar</button>
  </div>
  <div v-else-if="ui.aviso" class="toast" role="status">{{ ui.aviso }}</div>

  <div v-if="ui.confirmacion" class="modal" role="alertdialog" aria-modal="true">
    <div class="caja">
      <p>{{ ui.confirmacion.mensaje }}</p>
      <div class="fila-botones">
        <button class="btn btn-secundario" @click="ui.confirmacion.resolver(false)">Cancelar</button>
        <button class="btn btn-peligro-lleno" @click="ui.confirmacion.resolver(true)">{{ ui.confirmacion.boton }}</button>
      </div>
    </div>
  </div>
</template>
