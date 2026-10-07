<!-- Alta o cambio de nombre de un solicitante externo (Etapa 3.8, «Miembros y ajustes»). -->
<script setup lang="ts">
import { ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import type { PizarraDetalle, Solicitante } from "../tipos";
import { avisar } from "../ui";
import Hoja from "./Hoja.vue";

const props = defineProps<{ pizarraId: number; solicitante: Solicitante | null }>();
const emit = defineEmits<{ cerrar: []; guardado: [p: PizarraDetalle] }>();

const nombre = ref(props.solicitante?.nombre ?? "");
const error = ref("");
const ocupado = ref(false);

async function guardar() {
  error.value = "";
  if (!nombre.value.trim()) {
    error.value = "Escribe un nombre.";
    return;
  }
  ocupado.value = true;
  try {
    const datos = { nombre: nombre.value.trim() };
    const p = props.solicitante
      ? await api<PizarraDetalle>(`solicitantes/${props.solicitante.id}/`, "PATCH", datos)
      : await api<PizarraDetalle>(`pizarras/${props.pizarraId}/solicitantes/`, "POST", datos);
    avisar(props.solicitante ? "Se cambió el nombre." : "Se agregó el solicitante.");
    emit("guardado", p);
  } catch (e) {
    error.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <Hoja :titulo="solicitante ? 'Cambiar nombre' : 'Nuevo solicitante'" @cerrar="emit('cerrar')">
    <form novalidate @submit.prevent="guardar">
      <div class="campo">
        <label for="f-snombre">Nombre <span class="obligatorio" aria-hidden="true">*</span></label>
        <input id="f-snombre" v-model="nombre" aria-required="true" type="text" maxlength="100" placeholder="Ej. Dirección general" />
        <div v-if="error" class="error">{{ error }}</div>
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="emit('cerrar')">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">Guardar</button>
      </div>
    </form>
  </Hoja>
</template>
