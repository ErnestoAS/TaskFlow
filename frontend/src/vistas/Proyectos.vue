<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { mensajeDeError } from "../api";
import AvisoInstalacion from "../componentes/AvisoInstalacion.vue";
import Avatares from "../componentes/Avatares.vue";
import Cabecera from "../componentes/Cabecera.vue";
import FormProyecto from "../componentes/FormProyecto.vue";
import Icono from "../componentes/Icono.vue";
import { misProyectos, recargarProyectos } from "../proyectos";
import type { ProyectoDetalle, ProyectoResumen } from "../tipos";
import { avisar } from "../ui";
import { plural } from "../utilidades";

const router = useRouter();
const nuevo = ref(false);
const activos = computed(() => misProyectos.lista.filter((p) => !p.archivado));
const archivados = computed(() => misProyectos.lista.filter((p) => p.archivado));

onMounted(() => recargarProyectos().catch((e) => avisar(mensajeDeError(e, "No se pudieron cargar tus proyectos."))));

function porcentaje(p: ProyectoResumen, clave: "finalizada" | "en_curso") {
  const total = p.conteos.pendiente + p.conteos.en_curso + p.conteos.finalizada;
  return total ? `${(p.conteos[clave] / total) * 100}%` : "0";
}

async function creado(p: ProyectoDetalle) {
  nuevo.value = false;
  await recargarProyectos().catch(() => undefined);
  await router.push({ name: "tablero", params: { id: p.id } });
}
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Mis proyectos">
    <template #acciones>
      <button class="btn btn-chico btn-secundario" @click="nuevo = true"><Icono nombre="masChico" /> Nuevo proyecto</button>
    </template>
  </Cabecera>
  <main class="contenido">
    <AvisoInstalacion />
    <div class="seccion-titulo">Proyectos en los que participas</div>
    <div v-if="!misProyectos.cargados" class="cargando">Cargando…</div>
    <template v-else>
      <div class="lista-proyectos">
          <button
            v-for="p in activos"
            :key="p.id"
            class="proyecto"
            @click="router.push({ name: 'tablero', params: { id: p.id } })"
          >
            <div class="fila">
              <h3>{{ p.nombre }}</h3>
              <span v-if="p.rol === 'dueno'" class="etiqueta-rol">Dueña/o</span>
            </div>
            <div class="progreso" aria-hidden="true">
              <i :style="{ width: porcentaje(p, 'finalizada'), background: 'var(--tf-status-done)' }" />
              <i :style="{ width: porcentaje(p, 'en_curso'), background: 'var(--tf-status-progress)' }" />
            </div>
            <div class="conteos">
              <span class="chip pendiente"><span class="punto" />{{ plural(p.conteos.pendiente, "pendiente") }}</span>
              <span class="chip en_curso"><span class="punto" />{{ p.conteos.en_curso }} en curso</span>
              <span class="chip finalizada"><span class="punto" />{{ plural(p.conteos.finalizada, "finalizada") }}</span>
              <span v-if="p.conteos.vencidas" class="chip vencida"
                ><Icono nombre="alerta" /> {{ plural(p.conteos.vencidas, "vencida") }}</span
              >
            </div>
            <div class="fila">
              <Avatares :usuarios="p.miembros" :max="5" />
              <span v-if="p.dueno" style="font-size: 12px; color: var(--tf-text-muted); margin-left: auto"
                >Dueño: {{ p.dueno.nombre }}</span
              >
            </div>
          </button>
        <div v-if="!activos.length" class="vacio">Aún no participas en ningún proyecto. Crea uno o pide que te inviten.</div>
      </div>

      <template v-if="archivados.length">
        <div class="seccion-titulo">Archivados · {{ archivados.length }}</div>
        <div class="lista-proyectos">
          <button
            v-for="p in archivados"
            :key="p.id"
            class="proyecto archivado"
            @click="router.push({ name: 'tablero', params: { id: p.id } })"
          >
            <div class="fila">
              <h3>{{ p.nombre }}</h3>
              <span class="chip pendiente">Archivado</span>
              <span v-if="p.rol === 'dueno'" class="etiqueta-rol">Dueña/o</span>
            </div>
            <div class="conteos">
              <span class="chip finalizada"><span class="punto" />{{ plural(p.conteos.finalizada, "finalizada") }}</span>
              <span class="chip pendiente"
                ><span class="punto" />{{ p.conteos.pendiente + p.conteos.en_curso }} sin terminar</span
              >
            </div>
          </button>
        </div>
      </template>

      <div class="solo-telefono" style="margin-top: 14px">
        <button class="btn btn-secundario btn-bloque" @click="nuevo = true"><Icono nombre="masChico" /> Nuevo proyecto</button>
      </div>
      <div class="aviso" style="margin-top: 14px">
        <Icono nombre="info" />
        <span
          >Solo ves los proyectos de los que eres miembro. Cualquier usuario puede crear un proyecto; quien lo crea es su
          dueño y puede invitar a otras personas.</span
        >
      </div>
    </template>
  </main>
  <FormProyecto v-if="nuevo" @cerrar="nuevo = false" @guardado="creado" />
</template>
