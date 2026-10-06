<!--
  Tablero de una pizarra (§5, §4.6): sus listas en fila, con desplazamiento horizontal.
  - Teléfono: una lista por pantalla; arriba, pestañas con las listas (también se recorren
    deslizando) y un solo botón «Filtrar» que abre una hoja. Arrastrar: mantener presionada.
  - Computadora: columnas de 284 px con los filtros a la vista. Arrastrar con el mouse.
  - Orden manual dentro de cada lista; «Agregar tarjeta» al pie de cada lista y «Agregar lista»
    al final. Las opciones de una lista, en su «⋯».
-->
<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import { vArrastrable, type Soltado } from "../arrastre";
import Cabecera from "../componentes/Cabecera.vue";
import Chips from "../componentes/Chips.vue";
import Hoja from "../componentes/Hoja.vue";
import HojaLista from "../componentes/HojaLista.vue";
import Icono from "../componentes/Icono.vue";
import PanelTarjeta from "../componentes/PanelTarjeta.vue";
import TarjetaItem from "../componentes/TarjetaItem.vue";
import { recargarPizarras } from "../pizarras";
import { sesion } from "../sesion";
import type { Lista, PizarraDetalle, Tarjeta } from "../tipos";
import { avisar } from "../ui";
import { plural } from "../utilidades";

const props = defineProps<{ id: number }>();
const router = useRouter();

const pizarra = ref<PizarraDetalle | null>(null);
const tarjetas = ref<Tarjeta[]>([]);
const soloMias = ref(false);
const filtroTipo = ref<number | null>(null);
const filtrosAbiertos = ref(false);
const panel = ref<{ id: number | null; lista?: number } | null>(null);
const hojaLista = ref<Lista | null>(null);
const agregandoLista = ref(false);
const nombreLista = ref("");
const errorLista = ref("");
const listaVisible = ref<number | null>(null);
const tablero = ref<HTMLElement>();

async function cargar() {
  try {
    const [p, ts] = await Promise.all([
      api<PizarraDetalle>(`pizarras/${props.id}/`),
      api<Tarjeta[]>(`pizarras/${props.id}/tarjetas/`),
    ]);
    pizarra.value = p;
    tarjetas.value = ts;
    listaVisible.value = p.listas[0]?.id ?? null;
  } catch (e) {
    avisar(e instanceof ErrorApi && e.estado === 404 ? "Esa pizarra no existe o ya no eres miembro." : mensajeDeError(e));
    await router.replace({ name: "pizarras" });
  }
}
watch(
  () => props.id,
  () => {
    pizarra.value = null;
    soloMias.value = false;
    filtroTipo.value = null;
    panel.value = null;
    hojaLista.value = null;
    agregandoLista.value = false;
    cargar();
  },
  { immediate: true },
);

const permisos = computed(() => pizarra.value?.permisos);
const filtrando = computed(() => soloMias.value || !!filtroTipo.value);
const textoFiltros = computed(() =>
  [soloMias.value ? "Solo mías" : "", pizarra.value?.tipos.find((t) => t.id === filtroTipo.value)?.nombre ?? ""]
    .filter(Boolean)
    .join(" · "),
);
const pasaFiltro = (t: Tarjeta) =>
  (!soloMias.value || t.asignados.some((u) => u.id === sesion.usuario?.id)) &&
  (!filtroTipo.value || t.tipos.includes(filtroTipo.value));
const deLista = (listaId: number) =>
  tarjetas.value.filter((t) => t.lista === listaId).sort((a, b) => a.posicion - b.posicion);
const visibles = (listaId: number) => deLista(listaId).filter(pasaFiltro);
const sub = computed(() => {
  const p = pizarra.value;
  if (!p) return "";
  return `${plural(p.listas.length, "lista")} · ${plural(p.miembros.length, "miembro")}${p.archivada ? " · archivada" : ""}`;
});

async function refrescar() {
  try {
    const [p, ts] = await Promise.all([
      api<PizarraDetalle>(`pizarras/${props.id}/`),
      api<Tarjeta[]>(`pizarras/${props.id}/tarjetas/`),
    ]);
    pizarra.value = p;
    tarjetas.value = ts;
  } catch {
    /* se queda lo anterior */
  }
  recargarPizarras().catch(() => undefined);
}

/** Pone `t` en `listaId` antes de `antesDe` (o al final) y renumera, como hará el servidor. */
function colocar(t: Tarjeta, listaId: number, antesDe: number | null): number {
  const origen = t.lista;
  const destino = deLista(listaId).filter((x) => x.id !== t.id);
  let posicion = antesDe === null ? destino.length : destino.findIndex((x) => x.id === antesDe);
  if (posicion < 0) posicion = destino.length;
  destino.splice(posicion, 0, t);
  t.lista = listaId;
  destino.forEach((x, i) => (x.posicion = i));
  if (origen !== listaId) deLista(origen).forEach((x, i) => (x.posicion = i));
  return posicion;
}

async function alSoltar({ id, destino, antesDe }: Soltado) {
  const t = tarjetas.value.find((x) => x.id === id);
  const listaId = Number(destino.dataset.lista);
  if (!t || !listaId) return;
  const cambiaDeLista = t.lista !== listaId;
  // Con filtros, el índice visible no es el real: se calcula sobre la lista completa.
  const posicion = colocar(t, listaId, antesDe);
  try {
    const r = await api<Tarjeta>(`tarjetas/${id}/mover/`, "POST", { lista: listaId, posicion });
    Object.assign(t, { lista_nombre: r.lista_nombre, en_cierre: r.en_cierre });
    if (cambiaDeLista) {
      avisar(`Se movió a «${r.lista_nombre}».`);
      recargarPizarras().catch(() => undefined);
    }
  } catch (e) {
    avisar(mensajeDeError(e));
    refrescar();
  }
}

function saltarA(listaId: number) {
  listaVisible.value = listaId;
  tablero.value
    ?.querySelector(`[data-columna="${listaId}"]`)
    ?.scrollIntoView({ behavior: "smooth", inline: "start", block: "nearest" });
}

/** Teléfono: la pestaña marcada sigue a la lista que está a la vista al deslizar. */
function alDesplazar() {
  const t = tablero.value;
  if (!t) return;
  const columnas = [...t.querySelectorAll<HTMLElement>("[data-columna]")];
  const izquierda = t.getBoundingClientRect().left;
  const actual = columnas.find((c) => c.getBoundingClientRect().right - izquierda > c.offsetWidth / 2);
  if (actual) listaVisible.value = Number(actual.dataset.columna);
}

async function agregarLista() {
  errorLista.value = "";
  if (!nombreLista.value.trim()) {
    errorLista.value = "Escribe un nombre.";
    return;
  }
  try {
    pizarra.value = await api<PizarraDetalle>(`pizarras/${props.id}/listas/`, "POST", { nombre: nombreLista.value.trim() });
    avisar("Se agregó la lista.");
    nombreLista.value = "";
    agregandoLista.value = false;
    await nextTick();
    tablero.value?.scrollTo({ left: tablero.value.scrollWidth, behavior: "smooth" });
  } catch (e) {
    errorLista.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
  }
}

function listaActualizada(p: PizarraDetalle) {
  pizarra.value = p;
  // Renombrar o marcar de cierre cambia lo que muestran las tarjetas (nombre, vencidas).
  for (const t of tarjetas.value) {
    const l = p.listas.find((x) => x.id === t.lista);
    if (l) Object.assign(t, { lista_nombre: l.nombre, en_cierre: l.es_cierre });
  }
  recargarPizarras().catch(() => undefined);
}

async function restaurar() {
  try {
    pizarra.value = await api<PizarraDetalle>(`pizarras/${props.id}/restaurar/`, "POST");
    avisar("Se restauró la pizarra.");
    recargarPizarras().catch(() => undefined);
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

function quitarFiltros() {
  soloMias.value = false;
  filtroTipo.value = null;
  filtrosAbiertos.value = false;
}
</script>

<template>
  <Cabecera :titulo="pizarra?.nombre ?? 'Pizarra'" :sub="sub" :atras="{ name: 'pizarras' }">
    <template #acciones>
      <RouterLink :to="{ name: 'ajustes', params: { id } }" class="btn btn-chico btn-secundario"
        ><Icono nombre="personas" /> Miembros y ajustes</RouterLink
      >
    </template>
    <template #telefono>
      <RouterLink :to="{ name: 'ajustes', params: { id } }" class="btn-icono solo-telefono" aria-label="Miembros y ajustes"
        ><Icono nombre="personas"
      /></RouterLink>
    </template>
  </Cabecera>

  <main class="contenido contenido-tablero">
    <div v-if="!pizarra" class="cargando">Cargando…</div>
    <template v-else>
      <nav class="pestanas-listas solo-telefono" aria-label="Listas">
        <button
          v-for="l in pizarra.listas"
          :key="l.id"
          :aria-current="listaVisible === l.id ? 'true' : undefined"
          @click="saltarA(l.id)"
        >
          {{ l.nombre }}<span class="num">{{ visibles(l.id).length }}</span>
        </button>
      </nav>

      <div v-if="pizarra.archivada" class="banner">
        <Icono nombre="archivo" />
        <span>Pizarra archivada: se puede consultar, pero nadie puede crear, editar ni mover tarjetas.</span>
        <button v-if="pizarra.rol === 'dueno'" class="btn btn-chico btn-secundario" @click="restaurar">Restaurar</button>
      </div>

      <div class="barra-tel solo-telefono">
        <button class="btn btn-chico btn-secundario" @click="filtrosAbiertos = true">
          <Icono nombre="filtro" /> Filtrar<span v-if="filtrando" class="contador">{{
            (soloMias ? 1 : 0) + (filtroTipo ? 1 : 0)
          }}</span>
        </button>
        <span class="activos">{{
          filtrando ? textoFiltros : permisos?.mover ? "Mantén presionada una tarjeta para moverla." : ""
        }}</span>
        <button v-if="filtrando" class="btn-link" @click="quitarFiltros">Quitar</button>
      </div>

      <div class="filtros solo-computadora">
        <span>{{
          permisos?.mover ? "Arrastra las tarjetas para moverlas u ordenarlas." : plural(tarjetas.length, "tarjeta")
        }}</span>
        <button class="interruptor" :aria-pressed="soloMias" @click="soloMias = !soloMias">
          <span class="pista" />Solo mías
        </button>
      </div>
      <div v-if="pizarra.tipos.length" class="filtro-tipos solo-computadora" role="group" aria-label="Filtrar por tipo">
        <button :aria-pressed="!filtroTipo" @click="filtroTipo = null">Todos los tipos</button>
        <button
          v-for="tp in pizarra.tipos"
          :key="tp.id"
          :style="{ '--tipo': tp.color }"
          :aria-pressed="filtroTipo === tp.id"
          @click="filtroTipo = filtroTipo === tp.id ? null : tp.id"
        >
          <span class="punto" />{{ tp.nombre }}
        </button>
      </div>

      <div ref="tablero" class="tablero" @scroll.passive="alDesplazar">
        <section v-for="l in pizarra.listas" :key="l.id" class="lista" :data-columna="l.id" :aria-label="l.nombre">
          <div class="lista-cab">
            <span v-if="l.es_cierre" class="marca-cierre" title="Lista de cierre: lo que llega aquí cuenta como terminado"
              ><Icono nombre="palomitaCirculo"
            /></span>
            <h3 :title="l.nombre">{{ l.nombre }}</h3>
            <span class="num">{{ visibles(l.id).length }}</span>
            <button
              v-if="permisos?.gestionar_listas"
              class="btn-icono"
              :aria-label="`Opciones de la lista ${l.nombre}`"
              @click="hojaLista = l"
            >
              <Icono nombre="puntos" />
            </button>
          </div>
          <div
            v-arrastrable="{ grupo: `tarjetas-${pizarra.id}`, alSoltar, activo: !!permisos?.mover }"
            class="lista-tarjetas"
            :data-lista="l.id"
          >
            <TarjetaItem
              v-for="t in visibles(l.id)"
              :key="t.id"
              :tarjeta="t"
              :tipos="pizarra.tipos"
              @abrir="panel = { id: $event }"
            />
            <div v-if="!visibles(l.id).length" class="vacio">{{ filtrando ? "Nada con este filtro." : "Sin tarjetas." }}</div>
          </div>
          <button v-if="permisos?.crear" class="agregar-tarjeta" @click="panel = { id: null, lista: l.id }">
            <Icono nombre="masChico" /> Agregar tarjeta
          </button>
        </section>

        <section v-if="permisos?.gestionar_listas" class="lista nueva">
          <form v-if="agregandoLista" novalidate @submit.prevent="agregarLista">
            <input
              v-model="nombreLista"
              type="text"
              maxlength="50"
              placeholder="Nombre de la lista"
              aria-label="Nombre de la lista"
              autofocus
            />
            <div v-if="errorLista" class="error">{{ errorLista }}</div>
            <div class="fila-botones" style="margin: 0">
              <button type="button" class="btn btn-chico btn-secundario" @click="(agregandoLista = false), (errorLista = '')">
                Cancelar
              </button>
              <button type="submit" class="btn btn-chico btn-primario">Agregar lista</button>
            </div>
          </form>
          <button v-else class="agregar-tarjeta" @click="agregandoLista = true"><Icono nombre="masChico" /> Agregar lista</button>
        </section>
      </div>
    </template>
  </main>

  <PanelTarjeta
    v-if="panel && pizarra"
    :key="panel.id ?? `nueva-${panel.lista}`"
    :pizarra="pizarra"
    :tarjeta-id="panel.id"
    :lista-inicial="panel.lista"
    @cerrar="panel = null"
    @guardada="(t) => { if (!panel?.id) panel = { id: t.id }; refrescar(); }"
    @eliminada="refrescar"
    @abrir="(id) => (panel = { id })"
  />

  <HojaLista
    v-if="hojaLista && pizarra"
    :pizarra="pizarra"
    :lista="hojaLista"
    :n-tarjetas="deLista(hojaLista.id).length"
    @cerrar="hojaLista = null"
    @actualizada="listaActualizada"
  />

  <Hoja v-if="filtrosAbiertos && pizarra" titulo="Filtrar tarjetas" @cerrar="filtrosAbiertos = false">
    <div class="campo">
      <span class="etiqueta">Asignadas</span>
      <div class="opciones-filtro">
        <label><input v-model="soloMias" type="checkbox" />Solo las asignadas a mí</label>
      </div>
    </div>
    <div v-if="pizarra.tipos.length" class="campo">
      <span class="etiqueta">Tipo</span>
      <div class="opciones-filtro">
        <label><input v-model="filtroTipo" type="radio" name="fl-tipo" :value="null" />Todos los tipos</label>
        <label v-for="tp in pizarra.tipos" :key="tp.id"
          ><input v-model="filtroTipo" type="radio" name="fl-tipo" :value="tp.id" /><Chips :tipo="tp"
        /></label>
      </div>
    </div>
    <div class="fila-botones">
      <button type="button" class="btn btn-secundario" @click="quitarFiltros">Quitar filtros</button>
      <button type="button" class="btn btn-primario" @click="filtrosAbiertos = false">Ver tarjetas</button>
    </div>
  </Hoja>
</template>
