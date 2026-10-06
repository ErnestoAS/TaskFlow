<!-- Alta de pizarra, o cambio de nombre si recibe `pizarra`. -->
<script setup lang="ts">
import { ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import type { PizarraDetalle } from "../tipos";
import { avisar } from "../ui";
import Hoja from "./Hoja.vue";

const props = defineProps<{ pizarra?: PizarraDetalle }>();
const emit = defineEmits<{ cerrar: []; guardada: [p: PizarraDetalle] }>();

const nombre = ref(props.pizarra?.nombre ?? "");
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
    const p = props.pizarra
      ? await api<PizarraDetalle>(`pizarras/${props.pizarra.id}/`, "PATCH", { nombre: nombre.value.trim() })
      : await api<PizarraDetalle>("pizarras/", "POST", { nombre: nombre.value.trim() });
    avisar(props.pizarra ? "Se cambió el nombre." : "Se creó la pizarra.");
    emit("guardada", p);
  } catch (e) {
    error.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <Hoja :titulo="pizarra ? 'Cambiar nombre' : 'Nueva pizarra'" @cerrar="emit('cerrar')">
    <form novalidate @submit.prevent="guardar">
      <div class="campo">
        <label for="f-nombre">Nombre</label>
        <input id="f-nombre" v-model="nombre" type="text" maxlength="150" placeholder="Ej. Feria de empleo 2027" />
        <div v-if="error" class="error">{{ error }}</div>
      </div>
      <div v-if="!pizarra" class="campo">
        <div class="ayuda">
          Empieza vacía: en el tablero agregas las listas que necesites (por ejemplo «Pendiente», «En curso» y
          «Finalizada»). Serás el dueño: podrás invitar a otras personas y decidir qué puede hacer cada una.
        </div>
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="emit('cerrar')">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">
          {{ pizarra ? "Guardar" : "Crear pizarra" }}
        </button>
      </div>
    </form>
  </Hoja>
</template>
