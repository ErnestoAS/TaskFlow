<!-- Tarjetas asignadas a mí, sin finalizar, en mis proyectos activos; por fecha de fin. -->
<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api, mensajeDeError } from "../api";
import Cabecera from "../componentes/Cabecera.vue";
import Icono from "../componentes/Icono.vue";
import PanelTarjeta from "../componentes/PanelTarjeta.vue";
import TarjetaItem from "../componentes/TarjetaItem.vue";
import type { ProyectoDetalle, Tarjeta } from "../tipos";
import { avisar } from "../ui";
import { esVencida } from "../utilidades";

const tarjetas = ref<Tarjeta[] | null>(null);
// Detalle de cada proyecto (tipos y permisos), pedido una vez por proyecto.
const proyectos = ref<Record<number, ProyectoDetalle>>({});
const abierta = ref<{ id: number; proyecto: number } | null>(null);

const vencidas = computed(() => (tarjetas.value ?? []).filter(esVencida));
const resto = computed(() => (tarjetas.value ?? []).filter((t) => !esVencida(t)));

async function cargar() {
  try {
    tarjetas.value = await api<Tarjeta[]>("yo/tarjetas/");
    const ids = [...new Set(tarjetas.value.map((t) => t.proyecto))].filter((id) => !proyectos.value[id]);
    const detalles = await Promise.all(ids.map((id) => api<ProyectoDetalle>(`proyectos/${id}/`)));
    for (const d of detalles) proyectos.value[d.id] = d;
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudieron cargar tus tarjetas."));
    tarjetas.value ??= [];
  }
}
onMounted(cargar);

const tiposDe = (t: Tarjeta) => proyectos.value[t.proyecto]?.tipos ?? [];
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Mis tarjetas" />
  <main class="contenido">
    <div v-if="!tarjetas" class="cargando">Cargando…</div>
    <template v-else>
      <template v-if="vencidas.length">
        <div class="seccion-titulo">Vencidas · {{ vencidas.length }}</div>
        <div class="lista-proyectos">
          <TarjetaItem
            v-for="t in vencidas"
            :key="t.id"
            :tarjeta="t"
            :tipos="tiposDe(t)"
            con-proyecto
            @abrir="abierta = { id: t.id, proyecto: t.proyecto }"
          />
        </div>
      </template>
      <div class="seccion-titulo">Por hacer · {{ resto.length }}</div>
      <div class="lista-proyectos">
        <TarjetaItem
          v-for="t in resto"
          :key="t.id"
          :tarjeta="t"
          :tipos="tiposDe(t)"
          con-proyecto
          @abrir="abierta = { id: t.id, proyecto: t.proyecto }"
        />
      </div>
      <div v-if="!resto.length && !vencidas.length" class="vacio">No tienes tarjetas pendientes.</div>
      <div class="aviso" style="margin-top: 14px">
        <Icono nombre="info" />
        <span>Tarjetas asignadas a ti en todos tus proyectos que aún no están finalizadas, ordenadas por fecha de fin.</span>
      </div>
    </template>
  </main>

  <PanelTarjeta
    v-if="abierta && proyectos[abierta.proyecto]"
    :proyecto="proyectos[abierta.proyecto]"
    :tarjeta-id="abierta.id"
    @cerrar="(abierta = null), cargar()"
    @eliminada="cargar"
  />
</template>
