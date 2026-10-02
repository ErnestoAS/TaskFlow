<!--
  Tablero de un proyecto. Teléfono: pestañas por estatus y botón flotante «+». Computadora: tres
  columnas. Dentro de cada columna, por prioridad y luego por fecha de fin (como la API).
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Cabecera from "../componentes/Cabecera.vue";
import Icono from "../componentes/Icono.vue";
import PanelTarjeta from "../componentes/PanelTarjeta.vue";
import TarjetaItem from "../componentes/TarjetaItem.vue";
import { recargarProyectos } from "../proyectos";
import { sesion } from "../sesion";
import type { Estatus, ProyectoDetalle, Tarjeta } from "../tipos";
import { avisar } from "../ui";
import { ESTATUS, plural } from "../utilidades";

const props = defineProps<{ id: number }>();
const router = useRouter();

const proyecto = ref<ProyectoDetalle | null>(null);
const tarjetas = ref<Tarjeta[]>([]);
const tab = ref<Estatus>("pendiente");
const soloMias = ref(false);
const filtroTipo = ref<number | null>(null);
const panel = ref<{ id: number | null } | null>(null);

async function cargar() {
  try {
    const [p, ts] = await Promise.all([
      api<ProyectoDetalle>(`proyectos/${props.id}/`),
      api<Tarjeta[]>(`proyectos/${props.id}/tarjetas/`),
    ]);
    proyecto.value = p;
    tarjetas.value = ts;
  } catch (e) {
    avisar(e instanceof ErrorApi && e.estado === 404 ? "Ese proyecto no existe o ya no eres miembro." : mensajeDeError(e));
    await router.replace({ name: "proyectos" });
  }
}
watch(
  () => props.id,
  () => {
    proyecto.value = null;
    tab.value = "pendiente";
    soloMias.value = false;
    filtroTipo.value = null;
    panel.value = null;
    cargar();
  },
  { immediate: true },
);

const visibles = computed(() =>
  tarjetas.value.filter(
    (t) =>
      (!soloMias.value || t.asignados.some((u) => u.id === sesion.usuario?.id)) &&
      (!filtroTipo.value || t.tipos.includes(filtroTipo.value)),
  ),
);
const de = (e: Estatus) => visibles.value.filter((t) => t.estatus === e);
const VACIO: Record<Estatus, string> = {
  pendiente: "Sin tarjetas pendientes.",
  en_curso: "Sin tarjetas en curso.",
  finalizada: "Sin tarjetas finalizadas.",
};
const sub = computed(() => {
  const p = proyecto.value;
  if (!p) return "";
  return `${plural(p.miembros.length, "miembro")} · ${plural(tarjetas.value.length, "tarjeta")}${p.archivado ? " · archivado" : ""}`;
});

// Tras guardar o mover, se vuelve a pedir la lista para respetar el orden de la API.
async function refrescar() {
  try {
    tarjetas.value = await api<Tarjeta[]>(`proyectos/${props.id}/tarjetas/`);
  } catch {
    /* se queda la lista anterior */
  }
  recargarProyectos().catch(() => undefined);
}

async function restaurar() {
  try {
    proyecto.value = await api<ProyectoDetalle>(`proyectos/${props.id}/restaurar/`, "POST");
    avisar("Se restauró el proyecto.");
    recargarProyectos().catch(() => undefined);
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}
</script>

<template>
  <Cabecera :titulo="proyecto?.nombre ?? 'Proyecto'" :sub="sub" :atras="{ name: 'proyectos' }">
    <template #acciones>
      <RouterLink :to="{ name: 'ajustes', params: { id } }" class="btn btn-chico btn-secundario"
        ><Icono nombre="personas" /> Miembros y ajustes</RouterLink
      >
      <button v-if="proyecto?.permisos.crear" class="btn btn-chico btn-primario" @click="panel = { id: null }">
        <Icono nombre="masChico" /> Nueva tarjeta
      </button>
    </template>
    <template #telefono>
      <RouterLink :to="{ name: 'ajustes', params: { id } }" class="btn-icono solo-telefono" aria-label="Miembros y ajustes"
        ><Icono nombre="personas"
      /></RouterLink>
    </template>
  </Cabecera>

  <main class="contenido">
    <div v-if="!proyecto" class="cargando">Cargando…</div>
    <template v-else>
      <div v-if="proyecto.archivado" class="banner">
        <Icono nombre="archivo" />
        <span>Proyecto archivado: se puede consultar, pero nadie puede crear, editar ni mover tarjetas.</span>
        <button v-if="proyecto.rol === 'dueno'" class="btn btn-chico btn-secundario" @click="restaurar">Restaurar</button>
      </div>

      <div class="segmentos" role="group" aria-label="Estatus">
        <button v-for="[e, txt] in ESTATUS" :key="e" :class="e" :aria-pressed="tab === e" @click="tab = e">
          <span class="punto" />{{ txt }}<span class="num">{{ de(e).length }}</span>
        </button>
      </div>

      <div class="filtros">
        <span>{{ plural(visibles.length, "tarjeta") }}{{ soloMias ? " asignadas a ti" : "" }}</span>
        <button class="interruptor" :aria-pressed="soloMias" @click="soloMias = !soloMias">
          <span class="pista" />Solo mías
        </button>
      </div>

      <div v-if="proyecto.tipos.length" class="filtro-tipos" role="group" aria-label="Filtrar por tipo">
        <button :aria-pressed="!filtroTipo" @click="filtroTipo = null">Todos los tipos</button>
        <button
          v-for="tp in proyecto.tipos"
          :key="tp.id"
          :style="{ '--tipo': tp.color }"
          :aria-pressed="filtroTipo === tp.id"
          @click="filtroTipo = filtroTipo === tp.id ? null : tp.id"
        >
          <span class="punto" />{{ tp.nombre }}
        </button>
      </div>

      <div class="columnas">
        <section
          v-for="[e, txt] in ESTATUS"
          :key="e"
          class="columna"
          :class="{ 'solo-pestana': e !== tab }"
          :aria-label="txt"
        >
          <div class="columna-cab" :class="e">
            <span class="punto" />{{ txt }}<span class="num">{{ de(e).length }}</span>
          </div>
          <TarjetaItem
            v-for="t in de(e)"
            :key="t.id"
            :tarjeta="t"
            :tipos="proyecto.tipos"
            @abrir="panel = { id: $event }"
          />
          <div v-if="!de(e).length" class="vacio">{{ VACIO[e] }}</div>
        </section>
      </div>
    </template>
  </main>

  <button v-if="proyecto?.permisos.crear" class="fab" aria-label="Nueva tarjeta" @click="panel = { id: null }">
    <Icono nombre="mas" />
  </button>

  <PanelTarjeta
    v-if="panel && proyecto"
    :key="panel.id ?? 'nueva'"
    :proyecto="proyecto"
    :tarjeta-id="panel.id"
    @cerrar="panel = null"
    @guardada="(t) => { panel = { id: t.id }; refrescar(); }"
    @eliminada="refrescar"
  />
</template>
