<!-- Alta de proyecto, o cambio de nombre si recibe `proyecto`. -->
<script setup lang="ts">
import { ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import type { ProyectoDetalle } from "../tipos";
import { avisar } from "../ui";
import Hoja from "./Hoja.vue";

const props = defineProps<{ proyecto?: ProyectoDetalle }>();
const emit = defineEmits<{ cerrar: []; guardado: [p: ProyectoDetalle] }>();

const nombre = ref(props.proyecto?.nombre ?? "");
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
    const p = props.proyecto
      ? await api<ProyectoDetalle>(`proyectos/${props.proyecto.id}/`, "PATCH", { nombre: nombre.value.trim() })
      : await api<ProyectoDetalle>("proyectos/", "POST", { nombre: nombre.value.trim() });
    avisar(props.proyecto ? "Se cambió el nombre." : "Se creó el proyecto.");
    emit("guardado", p);
  } catch (e) {
    error.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <Hoja :titulo="proyecto ? 'Cambiar nombre' : 'Nuevo proyecto'" @cerrar="emit('cerrar')">
    <form novalidate @submit.prevent="guardar">
      <div class="campo">
        <label for="f-nombre">Nombre</label>
        <input id="f-nombre" v-model="nombre" type="text" maxlength="150" placeholder="Ej. Feria de empleo 2027" />
        <div v-if="error" class="error">{{ error }}</div>
      </div>
      <div v-if="!proyecto" class="campo">
        <div class="ayuda">
          Serás el dueño: podrás invitar a otras personas, decidir qué puede hacer cada una con las tarjetas, y
          después transferir, archivar o eliminar el proyecto.
        </div>
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="emit('cerrar')">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">
          {{ proyecto ? "Guardar" : "Crear proyecto" }}
        </button>
      </div>
    </form>
  </Hoja>
</template>
