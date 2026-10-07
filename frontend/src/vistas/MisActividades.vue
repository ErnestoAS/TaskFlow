<!--
  Actividades asignadas a mí en mis pizarras activas, en cualquier lista (§4.6), con la pizarra y la
  lista de cada una. Vencidas arriba; luego por fecha límite.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api, mensajeDeError } from "../api";
import Cabecera from "../componentes/Cabecera.vue";
import Icono from "../componentes/Icono.vue";
import PanelActividad from "../componentes/PanelActividad.vue";
import ActividadItem from "../componentes/ActividadItem.vue";
import type { PizarraDetalle, Actividad } from "../tipos";
import { avisar } from "../ui";
import { esVencida } from "../utilidades";

const actividades = ref<Actividad[] | null>(null);
// Detalle de cada pizarra (listas, tipos y permisos), pedido una vez por pizarra.
const pizarras = ref<Record<number, PizarraDetalle>>({});
const abierta = ref<{ id: number; pizarra: number } | null>(null);

const vencidas = computed(() => (actividades.value ?? []).filter(esVencida));
const resto = computed(() => (actividades.value ?? []).filter((t) => !esVencida(t)));

async function cargarPizarra(id: number) {
  if (!pizarras.value[id]) pizarras.value[id] = await api<PizarraDetalle>(`pizarras/${id}/`);
}

async function cargar() {
  try {
    actividades.value = await api<Actividad[]>("yo/actividades/");
    await Promise.all([...new Set(actividades.value.map((t) => t.pizarra))].map(cargarPizarra));
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudieron cargar tus actividades."));
    actividades.value ??= [];
  }
}
onMounted(cargar);

/** Abrir otra actividad desde el detalle (la de origen o una creada desde la checklist). */
async function abrir(id: number) {
  try {
    const t = await api<Actividad>(`actividades/${id}/`);
    await cargarPizarra(t.pizarra);
    abierta.value = { id, pizarra: t.pizarra };
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

const tiposDe = (t: Actividad) => pizarras.value[t.pizarra]?.tipos ?? [];
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Mis actividades" />
  <main class="contenido">
    <div v-if="!actividades" class="cargando">Cargando…</div>
    <template v-else>
      <template v-if="vencidas.length">
        <div class="seccion-titulo">Vencidas · {{ vencidas.length }}</div>
        <div class="mis-actividades">
          <ActividadItem
            v-for="t in vencidas"
            :key="t.id"
            :actividad="t"
            :tipos="tiposDe(t)"
            en-mis
            @abrir="abierta = { id: t.id, pizarra: t.pizarra }"
          />
        </div>
      </template>
      <div class="seccion-titulo">Asignadas a mí · {{ resto.length }}</div>
      <div class="mis-actividades">
        <ActividadItem
          v-for="t in resto"
          :key="t.id"
          :actividad="t"
          :tipos="tiposDe(t)"
          en-mis
          @abrir="abierta = { id: t.id, pizarra: t.pizarra }"
        />
      </div>
      <div v-if="!resto.length && !vencidas.length" class="vacio">No tienes actividades asignadas.</div>
      <div class="aviso" style="margin-top: 14px">
        <Icono nombre="info" />
        <span>Actividades asignadas a ti en tus pizarras activas, con la lista en la que están.</span>
      </div>
    </template>
  </main>

  <PanelActividad
    v-if="abierta && pizarras[abierta.pizarra]"
    :key="abierta.id"
    :pizarra="pizarras[abierta.pizarra]"
    :actividad-id="abierta.id"
    @cerrar="(abierta = null), cargar()"
    @eliminada="cargar"
    @abrir="abrir"
  />
</template>
