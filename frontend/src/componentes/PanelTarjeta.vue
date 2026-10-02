<!--
  Detalle de una tarjeta (estatus, historial, asignados) y su formulario de alta/edición, en la
  misma hoja. Lo que el usuario no puede hacer no se muestra o queda deshabilitado según los
  permisos que le dio el dueño (proyecto.permisos; todo en falso si el proyecto está archivado).
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { sesion } from "../sesion";
import type { Estatus, Prioridad, ProyectoDetalle, Tarjeta } from "../tipos";
import { avisar, confirmar } from "../ui";
import { ESTATUS, fechaHora, PRIORIDADES } from "../utilidades";
import Avatar from "./Avatar.vue";
import Chips from "./Chips.vue";
import Hoja from "./Hoja.vue";

const props = defineProps<{ proyecto: ProyectoDetalle; tarjetaId: number | null }>();
const emit = defineEmits<{ cerrar: []; guardada: [t: Tarjeta]; eliminada: [id: number] }>();

const tarjeta = ref<Tarjeta | null>(null);
const modo = ref<"ver" | "editar">(props.tarjetaId ? "ver" : "editar");
const cargando = ref(!!props.tarjetaId);
const ocupado = ref(false);
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");

const p = computed(() => props.proyecto);
const puede = computed(() => p.value.permisos);
const tiposDe = computed(() => p.value.tipos.filter((tp) => tarjeta.value?.tipos.includes(tp.id)));
const historial = computed(() => [...(tarjeta.value?.historial ?? [])].reverse());
const faltanPermisos = computed(
  () => !puede.value.cambiar_estatus || !puede.value.editar || !puede.value.eliminar,
);

const form = reactive({
  titulo: "",
  descripcion: "",
  prioridad: "media" as Prioridad,
  fecha_fin: "",
  tipos: [] as number[],
  asignados: [] as number[],
});

function llenarForm(t: Tarjeta | null) {
  form.titulo = t?.titulo ?? "";
  form.descripcion = t?.descripcion ?? "";
  form.prioridad = t?.prioridad ?? "media";
  form.fecha_fin = t?.fecha_fin ?? "";
  form.tipos = [...(t?.tipos ?? [])];
  form.asignados = (t?.asignados ?? []).map((u) => u.id);
}

async function cargar() {
  if (!props.tarjetaId) {
    llenarForm(null);
    return;
  }
  cargando.value = true;
  try {
    tarjeta.value = await api<Tarjeta>(`tarjetas/${props.tarjetaId}/`);
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudo abrir la tarjeta."));
    emit("cerrar");
  } finally {
    cargando.value = false;
  }
}
watch(() => props.tarjetaId, cargar, { immediate: true });

function editar() {
  llenarForm(tarjeta.value);
  errores.value = {};
  errorGeneral.value = "";
  modo.value = "editar";
}

async function guardar() {
  errores.value = {};
  errorGeneral.value = "";
  if (!form.titulo.trim()) {
    errores.value = { titulo: "Escribe un título." };
    return;
  }
  ocupado.value = true;
  const datos = { ...form, titulo: form.titulo.trim(), fecha_fin: form.fecha_fin || null };
  try {
    const t = tarjeta.value
      ? await api<Tarjeta>(`tarjetas/${tarjeta.value.id}/`, "PATCH", datos)
      : await api<Tarjeta>(`proyectos/${p.value.id}/tarjetas/`, "POST", datos);
    avisar(tarjeta.value ? "Se guardaron los cambios." : "Se creó la tarjeta.");
    tarjeta.value = t;
    modo.value = "ver";
    emit("guardada", t);
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function moverA(estatus: Estatus) {
  if (!tarjeta.value || tarjeta.value.estatus === estatus || ocupado.value) return;
  ocupado.value = true;
  try {
    const t = await api<Tarjeta>(`tarjetas/${tarjeta.value.id}/estatus/`, "POST", { estatus });
    tarjeta.value = t;
    emit("guardada", t);
    avisar(`Se movió a ${ESTATUS.find(([k]) => k === estatus)?.[1]}.`);
  } catch (e) {
    avisar(mensajeDeError(e));
  } finally {
    ocupado.value = false;
  }
}

async function eliminar() {
  const t = tarjeta.value;
  if (!t) return;
  const ok = await confirmar(`¿Eliminar la tarjeta «${t.titulo}»? Esta acción no se puede deshacer.`, "Eliminar");
  if (!ok) return;
  try {
    await api(`tarjetas/${t.id}/`, "DELETE");
    avisar("Se eliminó la tarjeta.");
    emit("eliminada", t.id);
    emit("cerrar");
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

function cancelar() {
  if (tarjeta.value) modo.value = "ver";
  else emit("cerrar");
}

const esYo = (id: number | undefined) => id === sesion.usuario?.id;
const titulo = computed(() =>
  modo.value === "editar" ? (tarjeta.value ? "Editar tarjeta" : "Nueva tarjeta") : (tarjeta.value?.titulo ?? "Tarjeta"),
);
</script>

<template>
  <Hoja :titulo="titulo" @cerrar="emit('cerrar')">
    <div v-if="cargando" class="cargando" style="min-height: 120px">Cargando…</div>

    <!-- Detalle -->
    <template v-else-if="modo === 'ver' && tarjeta">
      <div class="campo">
        <span class="etiqueta">Estatus</span>
        <div class="selector-estatus" role="group" aria-label="Cambiar estatus">
          <button
            v-for="[e, txt] in ESTATUS"
            :key="e"
            :class="e"
            :aria-pressed="tarjeta.estatus === e"
            :disabled="!puede.cambiar_estatus || ocupado"
            @click="moverA(e)"
          >
            <span class="punto" />{{ txt }}
          </button>
        </div>
      </div>
      <div class="campo"><span class="etiqueta">Prioridad</span><Chips :prioridad="tarjeta.prioridad" /></div>
      <div class="campo">
        <span class="etiqueta">Tipos</span>
        <div v-if="tiposDe.length" class="tipos-tarjeta"><Chips v-for="tp in tiposDe" :key="tp.id" :tipo="tp" /></div>
        <span v-else class="ayuda" style="font-size: 14px">Sin tipo</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Descripción</span>
        <p v-if="tarjeta.descripcion" class="texto-largo">{{ tarjeta.descripcion }}</p>
        <span v-else class="ayuda" style="font-size: 14px">Sin descripción</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Fecha fin</span>
        <Chips v-if="tarjeta.fecha_fin" :fecha="tarjeta" />
        <span v-else class="ayuda" style="font-size: 14px">Sin fecha</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Historial de estatus · {{ historial.length }}</span>
        <ul class="historial">
          <li v-for="(h, i) in historial" :key="i" :class="h.a">
            {{ h.usuario?.nombre ?? "Usuario eliminado" }}{{ esYo(h.usuario?.id) ? " (tú)" : "" }}
            <template v-if="h.de">
              la movió <span class="flecha">de</span> <Chips :estatus="h.de" /> <span class="flecha">a</span>
              <Chips :estatus="h.a" />
            </template>
            <template v-else>la creó en <Chips :estatus="h.a" /></template>
            <span class="cuando">{{ fechaHora(h.fecha) }}</span>
          </li>
        </ul>
      </div>
      <div class="campo">
        <span class="etiqueta">Asignada a · {{ tarjeta.asignados.length }}</span>
        <div class="personas">
          <div v-for="u in tarjeta.asignados" :key="u.id" class="persona">
            <Avatar :usuario="u" />
            <div class="nombre">{{ u.nombre }}{{ esYo(u.id) ? " (tú)" : "" }}</div>
          </div>
          <span v-if="!tarjeta.asignados.length" class="ayuda" style="font-size: 14px">Sin asignar</span>
        </div>
      </div>
      <div v-if="puede.editar || puede.eliminar" class="fila-botones">
        <button v-if="puede.editar" class="btn btn-secundario" @click="editar">Editar</button>
        <button v-if="puede.eliminar" class="btn btn-peligro" @click="eliminar">Eliminar</button>
      </div>
      <div class="meta">
        <span>Proyecto: {{ p.nombre }}</span>
        <span v-if="tarjeta.creada_por">Creada por {{ tarjeta.creada_por.nombre }}</span>
        <span v-if="p.archivado">Proyecto archivado: solo lectura.</span>
        <span v-else-if="faltanPermisos && p.dueno"
          >Lo que no ves disponible depende de los permisos que te dio el dueño ({{ p.dueno.nombre }}).</span
        >
      </div>
    </template>

    <!-- Alta / edición -->
    <form v-else novalidate @submit.prevent="guardar">
      <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
      <div class="campo">
        <label for="f-titulo">Título</label>
        <input id="f-titulo" v-model="form.titulo" type="text" maxlength="200" placeholder="¿Qué hay que hacer?" />
        <div v-if="errores.titulo" class="error">{{ errores.titulo }}</div>
      </div>
      <div class="campo">
        <label for="f-desc">Descripción</label>
        <textarea id="f-desc" v-model="form.descripcion" placeholder="Detalles, criterios de terminado…" />
        <div v-if="errores.descripcion" class="error">{{ errores.descripcion }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Prioridad</span>
        <div class="elegir-prioridad" role="radiogroup" aria-label="Prioridad">
          <label v-for="[k, txt] in PRIORIDADES" :key="k">
            <input v-model="form.prioridad" type="radio" name="prioridad" :value="k" />
            <span class="chip" :class="`prio-${k}`"><span class="punto" />{{ txt }}</span>
          </label>
        </div>
      </div>
      <div class="campo">
        <label for="f-fecha">Fecha fin <span style="text-transform: none; font-weight: 400">(opcional)</span></label>
        <input id="f-fecha" v-model="form.fecha_fin" type="date" />
        <div v-if="errores.fecha_fin" class="error">{{ errores.fecha_fin }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Tipos <span style="text-transform: none; font-weight: 400">(opcional, uno o más)</span></span>
        <div v-if="p.tipos.length" class="elegir-tipos">
          <label v-for="tp in p.tipos" :key="tp.id">
            <input v-model="form.tipos" type="checkbox" :value="tp.id" />
            <span class="chip tipo" :style="{ '--tipo': tp.color }"><span class="punto" />{{ tp.nombre }}</span>
          </label>
        </div>
        <div v-else class="ayuda">Este proyecto aún no tiene tipos.</div>
        <div v-if="errores.tipos" class="error">{{ errores.tipos }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Asignar a <span style="text-transform: none; font-weight: 400">(opcional)</span></span>
        <div class="personas">
          <label v-for="m in p.miembros" :key="m.usuario.id" class="persona">
            <input v-model="form.asignados" type="checkbox" :value="m.usuario.id" />
            <Avatar :usuario="m.usuario" />
            <span class="nombre">{{ m.usuario.nombre }}{{ esYo(m.usuario.id) ? " (tú)" : "" }}</span>
          </label>
        </div>
        <div class="ayuda">Solo aparecen los miembros de «{{ p.nombre }}». Puede quedar sin asignar.</div>
        <div v-if="errores.asignados" class="error">{{ errores.asignados }}</div>
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="cancelar">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">{{ ocupado ? "Guardando…" : "Guardar" }}</button>
      </div>
    </form>
  </Hoja>
</template>
