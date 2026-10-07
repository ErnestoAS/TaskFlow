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
import { misPizarras, recargarPizarras } from "./pizarras";
import { sesion } from "./sesion";
import { ui } from "./ui";

const route = useRoute();
const router = useRouter();

const conArmazon = computed(() => !route.meta.publica && !!sesion.usuario);

const SECCIONES: [string, string, NombreIcono][] = [
  ["pizarras", "Pizarras", "carpetas"],
  ["mis-actividades", "Mis actividades", "check"],
  ["perfil", "Perfil", "persona"],
];
const enPizarra = computed(() => route.name === "tablero" || route.name === "ajustes");
const pizarraActual = computed(() => (enPizarra.value ? Number(route.params.id) : null));
const seccionActiva = computed(() => (enPizarra.value ? "pizarras" : String(route.name)));
const activas = computed(() => misPizarras.lista.filter((p) => !p.archivada));

// La barra lateral necesita la lista de pizarras en cualquier pantalla.
watch(
  conArmazon,
  (si) => {
    if (si && !misPizarras.cargadas) recargarPizarras().catch(() => undefined);
  },
  { immediate: true },
);

// Versión nueva publicada: siempre se instala (§9). Se avisa con una cuenta regresiva para que
// nadie pierda lo que está escribiendo, y al llegar a cero se recarga sola.
const SEGUNDOS_PARA_ACTUALIZAR = 15;
const UNA_HORA = 60 * 60 * 1000;
const cuentaRegresiva = ref<number | null>(null);
let actualizar: ((recargar?: boolean) => Promise<void>) | undefined;

function iniciarCuentaRegresiva() {
  if (cuentaRegresiva.value !== null) return;
  cuentaRegresiva.value = SEGUNDOS_PARA_ACTUALIZAR;
  const reloj = setInterval(() => {
    if (cuentaRegresiva.value !== null && --cuentaRegresiva.value <= 0) {
      clearInterval(reloj);
      actualizar?.(true);
    }
  }, 1000);
}

if (import.meta.env.PROD) {
  actualizar = registerSW({
    onNeedRefresh: iniciarCuentaRegresiva,
    // El navegador solo busca versión nueva al abrir la app; una app instalada puede quedarse
    // abierta días. Se busca también al volver al frente y cada hora.
    onRegisteredSW(_url, registro) {
      if (!registro) return;
      const buscar = () => registro.update().catch(() => undefined);
      setInterval(buscar, UNA_HORA);
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") buscar();
      });
    },
  });
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
        :aria-current="!enPizarra && seccionActiva === nombre ? 'page' : undefined"
        @click="router.push({ name: nombre })"
      >
        <Icono :nombre="icono" /><span>{{ texto }}</span>
      </button>
      <template v-if="activas.length">
        <div class="separador" />
        <div class="rotulo-nav">Mis pizarras</div>
        <button
          v-for="p in activas"
          :key="p.id"
          :aria-current="pizarraActual === p.id ? 'page' : undefined"
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

  <div
    v-if="cuentaRegresiva !== null"
    class="toast"
    role="status"
    style="display: flex; gap: 12px; align-items: center"
  >
    TaskFlow se actualizará en {{ cuentaRegresiva }} s. Guarda lo que estés escribiendo.
    <button class="btn btn-chico btn-primario" @click="actualizar?.(true)">Actualizar ahora</button>
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
