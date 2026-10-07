<!--
  Tablero de una pizarra (§5, §4.6): sus listas en fila, con desplazamiento horizontal.
  - Teléfono: una lista por pantalla; arriba, pestañas con las listas (también se recorren
    deslizando) y un solo botón «Filtrar» que abre una hoja. Arrastrar: mantener presionada.
    Botón flotante «Agregar actividad» en la lista que está a la vista.
  - Computadora: columnas de 284 px con los filtros a la vista, que se desplazan por dentro para
    que «Agregar actividad» (al pie) quede siempre a la vista. Arrastrar con el mouse.
  - Filtros (Etapa 3.8): «Solo mías», uno o varios tipos (sale la que tenga cualquiera) y
    «Solicitada por».
  - Orden manual dentro de cada lista; «+» en el encabezado de cada lista (agrega arriba) y
    «Agregar lista» al final (Etapa 3.8). Las opciones de una lista, en su «⋯».
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
import PanelActividad from "../componentes/PanelActividad.vue";
import ActividadItem from "../componentes/ActividadItem.vue";
import { recargarPizarras } from "../pizarras";
import { sesion } from "../sesion";
import type { Lista, PizarraDetalle, Actividad } from "../tipos";
import { avisar } from "../ui";
import { plural } from "../utilidades";

const props = defineProps<{ id: number }>();
const router = useRouter();

const pizarra = ref<PizarraDetalle | null>(null);
const actividades = ref<Actividad[]>([]);
const soloMias = ref(false);
const filtroTipos = ref<number[]>([]);
/** «miembro:3» o «externo:5»; vacío = cualquiera. */
const filtroSolicitante = ref("");
const filtrosAbiertos = ref(false);
const panel = ref<{ id: number | null; lista?: number; arriba?: boolean } | null>(null);
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
      api<Actividad[]>(`pizarras/${props.id}/actividades/`),
    ]);
    pizarra.value = p;
    actividades.value = ts;
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
    filtroTipos.value = [];
    filtroSolicitante.value = "";
    panel.value = null;
    hojaLista.value = null;
    agregandoLista.value = false;
    cargar();
  },
  { immediate: true },
);

const permisos = computed(() => pizarra.value?.permisos);
const nFiltros = computed(
  () => (soloMias.value ? 1 : 0) + (filtroTipos.value.length ? 1 : 0) + (filtroSolicitante.value ? 1 : 0),
);
const filtrando = computed(() => nFiltros.value > 0);
/** Quienes pueden haber solicitado: los miembros y el catálogo de externos. */
const solicitantes = computed(() => {
  const p = pizarra.value;
  if (!p) return { miembros: [], externos: [] };
  return {
    miembros: p.miembros.map((m) => ({ clave: `miembro:${m.usuario.id}`, nombre: m.usuario.nombre })),
    externos: p.solicitantes.map((s) => ({ clave: `externo:${s.id}`, nombre: s.nombre })),
  };
});
const nombreSolicitante = computed(
  () =>
    [...solicitantes.value.miembros, ...solicitantes.value.externos].find((s) => s.clave === filtroSolicitante.value)
      ?.nombre ?? "",
);
const textoFiltros = computed(() =>
  [
    soloMias.value ? "Solo mías" : "",
    (pizarra.value?.tipos ?? [])
      .filter((t) => filtroTipos.value.includes(t.id))
      .map((t) => t.nombre)
      .join(", "),
    nombreSolicitante.value ? `Por ${nombreSolicitante.value}` : "",
  ]
    .filter(Boolean)
    .join(" · "),
);
const pasaFiltro = (t: Actividad) =>
  (!soloMias.value || t.asignados.some((u) => u.id === sesion.usuario?.id)) &&
  (!filtroTipos.value.length || t.tipos.some((id) => filtroTipos.value.includes(id))) &&
  (!filtroSolicitante.value ||
    (!!t.solicitante && `${t.solicitante.tipo}:${t.solicitante.id}` === filtroSolicitante.value));

function alternarTipo(id: number) {
  const i = filtroTipos.value.indexOf(id);
  if (i >= 0) filtroTipos.value.splice(i, 1);
  else filtroTipos.value.push(id);
}
const deLista = (listaId: number) =>
  actividades.value.filter((t) => t.lista === listaId).sort((a, b) => a.posicion - b.posicion);
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
      api<Actividad[]>(`pizarras/${props.id}/actividades/`),
    ]);
    pizarra.value = p;
    actividades.value = ts;
  } catch {
    /* se queda lo anterior */
  }
  recargarPizarras().catch(() => undefined);
}

/** Pone `t` en `listaId` antes de `antesDe` (o al final) y renumera, como hará el servidor. */
function colocar(t: Actividad, listaId: number, antesDe: number | null): number {
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
  const t = actividades.value.find((x) => x.id === id);
  const listaId = Number(destino.dataset.lista);
  if (!t || !listaId) return;
  const cambiaDeLista = t.lista !== listaId;
  // Con filtros, el índice visible no es el real: se calcula sobre la lista completa.
  const posicion = colocar(t, listaId, antesDe);
  try {
    const r = await api<Actividad>(`actividades/${id}/mover/`, "POST", { lista: listaId, posicion });
    t.lista_nombre = r.lista_nombre;
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
  // Renombrar cambia el nombre de lista que muestran las actividades.
  for (const t of actividades.value) {
    const l = p.listas.find((x) => x.id === t.lista);
    if (l) t.lista_nombre = l.nombre;
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
  filtroTipos.value = [];
  filtroSolicitante.value = "";
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
        <span>Pizarra archivada: se puede consultar, pero nadie puede crear, editar ni mover actividades.</span>
        <button v-if="pizarra.rol === 'dueno'" class="btn btn-chico btn-secundario" @click="restaurar">Restaurar</button>
      </div>

      <div class="barra-tel solo-telefono">
        <button class="btn btn-chico btn-secundario" @click="filtrosAbiertos = true">
          <Icono nombre="filtro" /> Filtrar<span v-if="filtrando" class="contador">{{ nFiltros }}</span>
        </button>
        <span class="activos">{{ filtrando ? textoFiltros : "" }}</span>
        <button v-if="filtrando" class="btn-link" @click="quitarFiltros">Quitar</button>
      </div>

      <div class="filtros solo-computadora">
        <span>{{ plural(actividades.length, "actividad") }}</span>
        <label class="filtro-solicitante">
          Solicitada por
          <select v-model="filtroSolicitante">
          <option value="">cualquiera</option>
          <optgroup label="Miembros">
            <option v-for="s in solicitantes.miembros" :key="s.clave" :value="s.clave">{{ s.nombre }}</option>
          </optgroup>
          <optgroup v-if="solicitantes.externos.length" label="Otras personas">
            <option v-for="s in solicitantes.externos" :key="s.clave" :value="s.clave">{{ s.nombre }}</option>
          </optgroup>
          </select>
        </label>
        <button class="interruptor" :aria-pressed="soloMias" @click="soloMias = !soloMias">
          <span class="pista" />Solo mías
        </button>
      </div>
      <div v-if="pizarra.tipos.length" class="filtro-tipos solo-computadora" role="group" aria-label="Filtrar por tipo">
        <button :aria-pressed="!filtroTipos.length" @click="filtroTipos = []">Todos los tipos</button>
        <button
          v-for="tp in pizarra.tipos"
          :key="tp.id"
          :style="{ '--tipo': tp.color }"
          :aria-pressed="filtroTipos.includes(tp.id)"
          @click="alternarTipo(tp.id)"
        >
          <span class="punto" />{{ tp.nombre }}
        </button>
      </div>

      <!-- Una pizarra nace sin listas (2026-10-06): cada quien arma las suyas. -->
      <div v-if="!pizarra.listas.length" class="aviso" style="margin-bottom: 12px">
        <Icono nombre="info" />
        <span>{{
          permisos?.gestionar_listas
            ? "Esta pizarra aún no tiene listas. Agrega la primera (por ejemplo «Pendiente») para empezar a crear actividades."
            : "Esta pizarra aún no tiene listas. Pídele al dueño que agregue la primera."
        }}</span>
      </div>
      <div ref="tablero" class="tablero" @scroll.passive="alDesplazar">
        <section v-for="l in pizarra.listas" :key="l.id" class="lista" :data-columna="l.id" :aria-label="l.nombre">
          <div class="lista-cab">
            <h3 :title="l.nombre">{{ l.nombre }}</h3>
            <span class="num">{{ visibles(l.id).length }}</span>
            <button
              v-if="permisos?.crear"
              class="btn-icono"
              :aria-label="`Agregar actividad arriba en ${l.nombre}`"
              title="Agregar actividad arriba"
              @click="panel = { id: null, lista: l.id, arriba: true }"
            >
              <Icono nombre="masChico" />
            </button>
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
            v-arrastrable="{ grupo: `actividades-${pizarra.id}`, alSoltar, activo: !!permisos?.mover }"
            class="lista-actividades"
            :data-lista="l.id"
          >
            <ActividadItem
              v-for="t in visibles(l.id)"
              :key="t.id"
              :actividad="t"
              :tipos="pizarra.tipos"
              @abrir="panel = { id: $event }"
            />
            <div v-if="!visibles(l.id).length" class="vacio">{{ filtrando ? "Nada con este filtro." : "Sin actividades." }}</div>
          </div>
          <button
            v-if="permisos?.crear"
            class="agregar-actividad solo-computadora"
            @click="panel = { id: null, lista: l.id }"
          >
            <Icono nombre="masChico" /> Agregar actividad
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
          <button v-else class="agregar-actividad" @click="agregandoLista = true"><Icono nombre="masChico" /> Agregar lista</button>
        </section>
      </div>
      <!-- Teléfono: agrega al final de la lista que está a la vista. -->
      <button
        v-if="permisos?.crear && listaVisible"
        class="btn-flotante solo-telefono"
        @click="panel = { id: null, lista: listaVisible }"
      >
        <Icono nombre="masChico" /> Agregar actividad
      </button>
    </template>
  </main>

  <PanelActividad
    v-if="panel && pizarra"
    :key="panel.id ?? `nueva-${panel.lista}-${panel.arriba ? 'arriba' : 'abajo'}`"
    :pizarra="pizarra"
    :actividad-id="panel.id"
    :lista-inicial="panel.lista"
    :arriba="panel.arriba"
    @cerrar="panel = null"
    @guardada="(t) => { if (!panel?.id) panel = { id: t.id }; refrescar(); }"
    @eliminada="refrescar"
    @abrir="(id) => (panel = { id })"
  />

  <HojaLista
    v-if="hojaLista && pizarra"
    :pizarra="pizarra"
    :lista="hojaLista"
    :n-actividades="deLista(hojaLista.id).length"
    @cerrar="hojaLista = null"
    @actualizada="listaActualizada"
  />

  <Hoja v-if="filtrosAbiertos && pizarra" titulo="Filtrar actividades" @cerrar="filtrosAbiertos = false">
    <div class="campo">
      <span class="etiqueta">Asignadas</span>
      <div class="opciones-filtro">
        <label><input v-model="soloMias" type="checkbox" />Solo las asignadas a mí</label>
      </div>
    </div>
    <div v-if="pizarra.tipos.length" class="campo">
      <span class="etiqueta">Tipos</span>
      <div class="opciones-filtro">
        <label v-for="tp in pizarra.tipos" :key="tp.id"
          ><input v-model="filtroTipos" type="checkbox" :value="tp.id" /><Chips :tipo="tp"
        /></label>
      </div>
    </div>
    <div class="campo">
      <label for="fl-solicitante">Solicitada por</label>
      <select id="fl-solicitante" v-model="filtroSolicitante">
        <option value="">Cualquiera</option>
        <optgroup label="Miembros">
          <option v-for="s in solicitantes.miembros" :key="s.clave" :value="s.clave">{{ s.nombre }}</option>
        </optgroup>
        <optgroup v-if="solicitantes.externos.length" label="Otras personas">
          <option v-for="s in solicitantes.externos" :key="s.clave" :value="s.clave">{{ s.nombre }}</option>
        </optgroup>
      </select>
    </div>
    <div class="fila-botones">
      <button type="button" class="btn btn-secundario" @click="quitarFiltros">Quitar filtros</button>
      <button type="button" class="btn btn-primario" @click="filtrosAbiertos = false">Ver actividades</button>
    </div>
  </Hoja>
</template>
