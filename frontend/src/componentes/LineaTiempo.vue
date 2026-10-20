<!--
  Sección «Actividad» de una actividad (2026-10-20, §5): la caja para comentar y una sola línea de
  tiempo, más reciente arriba, con los comentarios y los movimientos del historial, como en Trello.
  Comenta cualquier miembro; edita solo el autor; borra el autor o el dueño (§4.4). Nada en una
  pizarra archivada. Se guarda al momento, sin el «Guardar» del formulario. El texto sin publicar
  va en `v-model:borrador`, para que el panel pregunte antes de cerrarse.
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { sesion } from "../sesion";
import type { Actividad, Comentario, Movimiento, PizarraDetalle } from "../tipos";
import { avisar, confirmar } from "../ui";
import { fechaHora } from "../utilidades";
import Avatar from "./Avatar.vue";
import Chips from "./Chips.vue";

const MAX_TEXTO = 2000;

const props = defineProps<{ actividad: Actividad; pizarra: PizarraDetalle }>();
const emit = defineEmits<{ actualizada: [t: Actividad] }>();
const borrador = defineModel<string>("borrador", { default: "" });

type Entrada = { clave: string; fecha: number } & (
  | { comentario: Comentario; movimiento?: undefined }
  | { movimiento: Movimiento; comentario?: undefined }
);

const entradas = computed<Entrada[]>(() =>
  [
    ...(props.actividad.comentarios ?? []).map((c) => ({
      clave: `c${c.id}`,
      fecha: Date.parse(c.creado_en),
      comentario: c,
    })),
    ...(props.actividad.historial ?? []).map((m, i) => ({
      clave: `m${i}`,
      fecha: Date.parse(m.fecha),
      movimiento: m,
    })),
  ].sort((a, b) => b.fecha - a.fecha),
);

const activa = computed(() => !props.pizarra.archivada);
const esYo = (id: number | undefined) => id === sesion.usuario?.id;
const puedeEditar = (c: Comentario) => activa.value && esYo(c.autor?.id);
const puedeBorrar = (c: Comentario) => activa.value && (esYo(c.autor?.id) || props.pizarra.rol === "dueno");

const ocupado = ref(false);
const error = ref("");
const editando = ref<number | null>(null);
const textoEditado = ref("");
const errorEdicion = ref("");

async function publicar() {
  const texto = borrador.value.trim();
  if (!texto || ocupado.value) return;
  ocupado.value = true;
  error.value = "";
  try {
    emit("actualizada", await api<Actividad>(`actividades/${props.actividad.id}/comentarios/`, "POST", { texto }));
    borrador.value = "";
  } catch (e) {
    error.value = e instanceof ErrorApi ? (e.campos.texto ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

function editar(c: Comentario) {
  editando.value = c.id;
  textoEditado.value = c.texto;
  errorEdicion.value = "";
}

async function guardarEdicion(c: Comentario) {
  const texto = textoEditado.value.trim();
  if (!texto) {
    errorEdicion.value = "Escribe el comentario.";
    return;
  }
  ocupado.value = true;
  try {
    emit("actualizada", await api<Actividad>(`comentarios/${c.id}/`, "PATCH", { texto }));
    editando.value = null;
  } catch (e) {
    errorEdicion.value = e instanceof ErrorApi ? (e.campos.texto ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function eliminar(c: Comentario) {
  const ok = await confirmar("¿Eliminar el comentario? Esta acción no se puede deshacer.", "Eliminar");
  if (!ok) return;
  try {
    emit("actualizada", await api<Actividad>(`comentarios/${c.id}/`, "DELETE"));
    avisar("Se eliminó el comentario.");
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}
</script>

<template>
  <div class="campo">
    <span class="etiqueta">Actividad</span>
    <div v-if="activa" class="nuevo-comentario">
      <textarea
        v-model="borrador"
        :maxlength="MAX_TEXTO"
        placeholder="Escribe un comentario…"
        aria-label="Escribe un comentario"
        @keydown.ctrl.enter.prevent="publicar"
        @keydown.meta.enter.prevent="publicar"
      />
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="borrador.trim()" class="fila">
        <button type="button" class="btn btn-chico btn-primario" :disabled="ocupado" @click="publicar">
          {{ ocupado ? "Publicando…" : "Comentar" }}
        </button>
      </div>
    </div>

    <ul class="linea-tiempo">
      <li v-for="e in entradas" :key="e.clave" :class="e.comentario ? 'comentario' : 'movimiento'">
        <template v-if="e.comentario">
          <div class="lado">
            <Avatar v-if="e.comentario.autor" :usuario="e.comentario.autor" />
            <span v-else class="avatar grande mas" aria-hidden="true">?</span>
          </div>
          <div class="cuerpo">
            <div>
              <span class="autor"
                >{{ e.comentario.autor?.nombre ?? "Usuario eliminado"
                }}{{ esYo(e.comentario.autor?.id) ? " (tú)" : "" }}</span
              >
              <span class="cuando">
                · {{ fechaHora(e.comentario.creado_en) }}<template v-if="e.comentario.editado_en"> (editado)</template></span
              >
            </div>
            <template v-if="editando === e.comentario.id">
              <textarea
                v-model="textoEditado"
                :maxlength="MAX_TEXTO"
                aria-label="Editar el comentario"
                @keydown.ctrl.enter.prevent="guardarEdicion(e.comentario!)"
                @keydown.esc.stop.prevent="editando = null"
              />
              <div v-if="errorEdicion" class="error">{{ errorEdicion }}</div>
              <div class="acciones">
                <button type="button" class="btn btn-chico btn-secundario" @click="editando = null">Cancelar</button>
                <button
                  type="button"
                  class="btn btn-chico btn-primario"
                  :disabled="ocupado"
                  @click="guardarEdicion(e.comentario!)"
                >
                  Guardar
                </button>
              </div>
            </template>
            <template v-else>
              <!-- Texto plano escapado por Vue (nunca v-html, §7); los saltos de línea los respeta el CSS. -->
              <p class="burbuja">{{ e.comentario.texto }}</p>
              <div v-if="puedeEditar(e.comentario) || puedeBorrar(e.comentario)" class="acciones">
                <button
                  v-if="puedeEditar(e.comentario)"
                  type="button"
                  class="btn btn-chico btn-secundario"
                  @click="editar(e.comentario!)"
                >
                  Editar
                </button>
                <button
                  v-if="puedeBorrar(e.comentario)"
                  type="button"
                  class="btn btn-chico btn-peligro"
                  @click="eliminar(e.comentario!)"
                >
                  Eliminar
                </button>
              </div>
            </template>
          </div>
        </template>
        <template v-else-if="e.movimiento">
          <div class="lado"><span class="punto-mov" /></div>
          <div class="cuerpo">
            {{ e.movimiento.usuario?.nombre ?? "Usuario eliminado" }}{{ esYo(e.movimiento.usuario?.id) ? " (tú)" : "" }}
            <template v-if="e.movimiento.nota">{{ e.movimiento.nota }}</template>
            <template v-else-if="e.movimiento.de"
              >la movió de <Chips :lista="e.movimiento.de" /> a <Chips :lista="e.movimiento.a ?? ''"
            /></template>
            <template v-else>la creó en <Chips :lista="e.movimiento.a ?? ''" /></template>
            <span class="cuando"> · {{ fechaHora(e.movimiento.fecha) }}</span>
          </div>
        </template>
      </li>
    </ul>
  </div>
</template>
