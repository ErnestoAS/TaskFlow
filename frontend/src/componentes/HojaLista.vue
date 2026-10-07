<!--
  Opciones de una lista (§4.6): renombrar, moverla a la izquierda o a la derecha y eliminarla (solo
  vacía). Permiso «Gestionar listas». Cada cambio devuelve la pizarra.
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import type { Lista, PizarraDetalle } from "../tipos";
import { avisar, confirmar } from "../ui";
import { plural } from "../utilidades";
import Hoja from "./Hoja.vue";
import Icono from "./Icono.vue";

const props = defineProps<{ pizarra: PizarraDetalle; lista: Lista; nActividades: number }>();
const emit = defineEmits<{ cerrar: []; actualizada: [p: PizarraDetalle] }>();

const nombre = ref(props.lista.nombre);
const error = ref("");
const ocupado = ref(false);

const indice = computed(() => props.pizarra.listas.findIndex((l) => l.id === props.lista.id));
const actual = computed(() => props.pizarra.listas[indice.value] ?? props.lista);

async function enviar(ruta: string, metodo: "POST" | "PATCH" | "DELETE", datos: unknown, aviso: string) {
  ocupado.value = true;
  error.value = "";
  try {
    emit("actualizada", await api<PizarraDetalle>(ruta, metodo, datos));
    avisar(aviso);
    return true;
  } catch (e) {
    error.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
    return false;
  } finally {
    ocupado.value = false;
  }
}

async function renombrar() {
  if (!nombre.value.trim()) {
    error.value = "Escribe un nombre.";
    return;
  }
  if (nombre.value.trim() === actual.value.nombre) return;
  await enviar(`listas/${props.lista.id}/`, "PATCH", { nombre: nombre.value.trim() }, "Se renombró la lista.");
}

function mover(paso: -1 | 1) {
  const ids = props.pizarra.listas.map((l) => l.id);
  const [id] = ids.splice(indice.value, 1);
  ids.splice(indice.value + paso, 0, id);
  enviar(`pizarras/${props.pizarra.id}/listas/orden/`, "POST", { ids }, "Se cambió el orden de las listas.");
}

async function eliminar() {
  const ok = await confirmar(`¿Eliminar la lista «${actual.value.nombre}»? Esta acción no se puede deshacer.`, "Eliminar lista");
  if (ok && (await enviar(`listas/${props.lista.id}/`, "DELETE", undefined, "Se eliminó la lista."))) emit("cerrar");
}
</script>

<template>
  <Hoja :titulo="`Lista «${actual.nombre}»`" @cerrar="emit('cerrar')">
    <div v-if="error" class="error-general" role="alert">{{ error }}</div>
    <form class="campo" novalidate @submit.prevent="renombrar">
      <label for="f-lnombre">Nombre <span class="obligatorio" aria-hidden="true">*</span></label>
      <div class="linea-campo">
        <input id="f-lnombre" aria-required="true" v-model="nombre" type="text" maxlength="50" />
        <button type="submit" class="btn btn-primario" :disabled="ocupado">Guardar</button>
      </div>
    </form>
    <div class="campo">
      <span class="etiqueta">Orden en la pizarra</span>
      <div class="fila-botones">
        <button class="btn btn-secundario" :disabled="ocupado || indice <= 0" @click="mover(-1)">
          <Icono nombre="izquierda" /> A la izquierda
        </button>
        <button class="btn btn-secundario" :disabled="ocupado || indice >= pizarra.listas.length - 1" @click="mover(1)">
          A la derecha <Icono nombre="derecha" />
        </button>
      </div>
    </div>
    <div class="campo">
      <span class="etiqueta">Eliminar</span>
      <button class="btn btn-chico btn-peligro" :disabled="ocupado || nActividades > 0" @click="eliminar">Eliminar lista</button>
      <!-- No es ayuda: dice por qué el botón está deshabilitado. -->
      <div v-if="nActividades" class="ayuda">Tiene {{ plural(nActividades, "actividad") }}: muévelas o elimínalas antes.</div>
    </div>
  </Hoja>
</template>
