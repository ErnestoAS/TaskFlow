<!--
  Tarjetas asignadas a mí en mis pizarras activas, en cualquier lista (§4.6), con la pizarra y la
  lista de cada una. Vencidas arriba; luego por fecha límite.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api, mensajeDeError } from "../api";
import Cabecera from "../componentes/Cabecera.vue";
import Icono from "../componentes/Icono.vue";
import PanelTarjeta from "../componentes/PanelTarjeta.vue";
import TarjetaItem from "../componentes/TarjetaItem.vue";
import type { PizarraDetalle, Tarjeta } from "../tipos";
import { avisar } from "../ui";
import { esVencida } from "../utilidades";

const tarjetas = ref<Tarjeta[] | null>(null);
// Detalle de cada pizarra (listas, tipos y permisos), pedido una vez por pizarra.
const pizarras = ref<Record<number, PizarraDetalle>>({});
const abierta = ref<{ id: number; pizarra: number } | null>(null);

const vencidas = computed(() => (tarjetas.value ?? []).filter(esVencida));
const resto = computed(() => (tarjetas.value ?? []).filter((t) => !esVencida(t)));

async function cargarPizarra(id: number) {
  if (!pizarras.value[id]) pizarras.value[id] = await api<PizarraDetalle>(`pizarras/${id}/`);
}

async function cargar() {
  try {
    tarjetas.value = await api<Tarjeta[]>("yo/tarjetas/");
    await Promise.all([...new Set(tarjetas.value.map((t) => t.pizarra))].map(cargarPizarra));
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudieron cargar tus tarjetas."));
    tarjetas.value ??= [];
  }
}
onMounted(cargar);

/** Abrir otra tarjeta desde el detalle (la de origen o una creada desde la checklist). */
async function abrir(id: number) {
  try {
    const t = await api<Tarjeta>(`tarjetas/${id}/`);
    await cargarPizarra(t.pizarra);
    abierta.value = { id, pizarra: t.pizarra };
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

const tiposDe = (t: Tarjeta) => pizarras.value[t.pizarra]?.tipos ?? [];
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Mis tarjetas" />
  <main class="contenido">
    <div v-if="!tarjetas" class="cargando">Cargando…</div>
    <template v-else>
      <template v-if="vencidas.length">
        <div class="seccion-titulo">Vencidas · {{ vencidas.length }}</div>
        <div class="mis-tarjetas">
          <TarjetaItem
            v-for="t in vencidas"
            :key="t.id"
            :tarjeta="t"
            :tipos="tiposDe(t)"
            en-mis
            @abrir="abierta = { id: t.id, pizarra: t.pizarra }"
          />
        </div>
      </template>
      <div class="seccion-titulo">Asignadas a mí · {{ resto.length }}</div>
      <div class="mis-tarjetas">
        <TarjetaItem
          v-for="t in resto"
          :key="t.id"
          :tarjeta="t"
          :tipos="tiposDe(t)"
          en-mis
          @abrir="abierta = { id: t.id, pizarra: t.pizarra }"
        />
      </div>
      <div v-if="!resto.length && !vencidas.length" class="vacio">No tienes tarjetas asignadas.</div>
      <div class="aviso" style="margin-top: 14px">
        <Icono nombre="info" />
        <span>Tarjetas asignadas a ti en tus pizarras activas, con la lista en la que están.</span>
      </div>
    </template>
  </main>

  <PanelTarjeta
    v-if="abierta && pizarras[abierta.pizarra]"
    :key="abierta.id"
    :pizarra="pizarras[abierta.pizarra]"
    :tarjeta-id="abierta.id"
    @cerrar="(abierta = null), cargar()"
    @eliminada="cargar"
    @abrir="abrir"
  />
</template>
