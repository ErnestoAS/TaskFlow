<!-- Mis pizarras (§5): activas y archivadas, cada una con un resumen de tamaño fijo. -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { mensajeDeError } from "../api";
import AvisoInstalacion from "../componentes/AvisoInstalacion.vue";
import Avatares from "../componentes/Avatares.vue";
import Cabecera from "../componentes/Cabecera.vue";
import FormPizarra from "../componentes/FormPizarra.vue";
import Icono from "../componentes/Icono.vue";
import { misPizarras, recargarPizarras } from "../pizarras";
import type { PizarraDetalle } from "../tipos";
import { avisar } from "../ui";
import { plural } from "../utilidades";

const router = useRouter();
const nueva = ref(false);
const activas = computed(() => misPizarras.lista.filter((p) => !p.archivada));
const archivadas = computed(() => misPizarras.lista.filter((p) => p.archivada));
const secciones = computed(() => [
  { titulo: "", pizarras: activas.value },
  ...(archivadas.value.length ? [{ titulo: `Archivadas · ${archivadas.value.length}`, pizarras: archivadas.value }] : []),
]);

onMounted(() => recargarPizarras().catch((e) => avisar(mensajeDeError(e, "No se pudieron cargar tus pizarras."))));

async function creada(p: PizarraDetalle) {
  nueva.value = false;
  await recargarPizarras().catch(() => undefined);
  await router.push({ name: "tablero", params: { id: p.id } });
}
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Mis pizarras">
    <template #acciones>
      <button class="btn btn-chico btn-primario" @click="nueva = true"><Icono nombre="masChico" /> Nueva pizarra</button>
    </template>
  </Cabecera>
  <main class="contenido">
    <AvisoInstalacion />
    <div class="seccion-titulo">Pizarras en las que participas</div>
    <div v-if="!misPizarras.cargadas" class="cargando">Cargando…</div>
    <template v-else>
      <template v-for="seccion in secciones" :key="seccion.titulo">
      <div v-if="seccion.titulo" class="seccion-titulo">{{ seccion.titulo }}</div>
      <div class="lista-pizarras">
        <button
          v-for="p in seccion.pizarras"
          :key="p.id"
          class="pizarra"
          :class="{ archivada: p.archivada }"
          @click="router.push({ name: 'tablero', params: { id: p.id } })"
        >
          <div class="fila">
            <h3>{{ p.nombre }}</h3>
            <span v-if="p.archivada" class="chip neutro">Archivada</span>
            <span v-if="p.rol === 'dueno'" class="etiqueta-rol">Dueña/o</span>
          </div>
          <!-- Una sola línea, tenga las listas que tenga (§4.6). -->
          <div class="resumen">
            <span
              ><b>{{ p.conteos.tarjetas }}</b> {{ p.conteos.tarjetas === 1 ? "tarjeta" : "tarjetas" }} ·
              <b>{{ p.conteos.listas }}</b> {{ p.conteos.listas === 1 ? "lista" : "listas"
              }}<template v-if="p.conteos.mias">
                · <b>{{ p.conteos.mias }}</b> {{ p.conteos.mias === 1 ? "tuya" : "tuyas" }}</template
              ></span
            >
          </div>
          <div class="fila">
            <Avatares :usuarios="p.miembros" :max="5" />
            <span v-if="p.conteos.vencidas" class="chip vencida"
              ><Icono nombre="alerta" /> {{ plural(p.conteos.vencidas, "vencida") }}</span
            >
          </div>
        </button>
        <div v-if="!seccion.titulo && !activas.length" class="vacio">
          Aún no participas en ninguna pizarra. Crea una o pide que te inviten.
        </div>
      </div>
      </template>

      <div class="solo-telefono" style="margin-top: 14px">
        <button class="btn btn-primario btn-bloque" @click="nueva = true"><Icono nombre="masChico" /> Nueva pizarra</button>
      </div>
      <div class="aviso" style="margin-top: 14px">
        <Icono nombre="info" />
        <span
          >Solo ves las pizarras de las que eres miembro. Cualquier usuario puede crear una; quien la crea es su dueño y
          puede invitar a otras personas.</span
        >
      </div>
    </template>
  </main>
  <FormPizarra v-if="nueva" @cerrar="nueva = false" @guardada="creada" />
</template>
