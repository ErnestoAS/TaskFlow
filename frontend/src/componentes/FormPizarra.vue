<!--
  Alta de pizarra, o cambio de nombre si recibe `pizarra`. Al crear, «Empezar con» (2026-10-20):
  una plantilla de listas, las de otra pizarra propia o ninguna (§4.5).
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { misPizarras } from "../pizarras";
import type { PizarraDetalle } from "../tipos";
import { avisar } from "../ui";
import { PLANTILLAS_LISTAS } from "../utilidades";
import Hoja from "./Hoja.vue";

const props = defineProps<{ pizarra?: PizarraDetalle }>();
const emit = defineEmits<{ cerrar: []; guardada: [p: PizarraDetalle] }>();

const nombre = ref(props.pizarra?.nombre ?? "");
const plantilla = ref("basica");
/** Solo las que tienen listas: copiar una vacía sería «Sin listas». */
const copiables = computed(() => misPizarras.lista.filter((p) => p.conteos.listas > 0));
const copiarDe = ref<number | null>(copiables.value[0]?.id ?? null);
const error = ref("");
const errorPlantilla = ref("");
const ocupado = ref(false);

async function guardar() {
  error.value = "";
  errorPlantilla.value = "";
  if (!nombre.value.trim()) {
    error.value = "Escribe un nombre.";
    return;
  }
  ocupado.value = true;
  try {
    const p = props.pizarra
      ? await api<PizarraDetalle>(`pizarras/${props.pizarra.id}/`, "PATCH", { nombre: nombre.value.trim() })
      : await api<PizarraDetalle>("pizarras/", "POST", {
          nombre: nombre.value.trim(),
          plantilla: plantilla.value,
          copiar_de: plantilla.value === "copiar" ? copiarDe.value : null,
        });
    avisar(props.pizarra ? "Se cambió el nombre." : "Se creó la pizarra.");
    emit("guardada", p);
  } catch (e) {
    if (e instanceof ErrorApi && (e.campos.plantilla || e.campos.copiar_de)) {
      errorPlantilla.value = e.campos.plantilla ?? e.campos.copiar_de;
    } else error.value = e instanceof ErrorApi ? (e.campos.nombre ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <Hoja :titulo="pizarra ? 'Cambiar nombre' : 'Nueva pizarra'" @cerrar="emit('cerrar')">
    <form novalidate @submit.prevent="guardar">
      <div class="campo">
        <label for="f-nombre">Nombre <span class="obligatorio" aria-hidden="true">*</span></label>
        <input id="f-nombre" aria-required="true" v-model="nombre" type="text" maxlength="150" placeholder="Ej. Feria de empleo 2027" />
        <div v-if="error" class="error">{{ error }}</div>
      </div>
      <div v-if="!pizarra" class="campo">
        <span class="etiqueta">Empezar con</span>
        <div class="opciones-filtro" role="radiogroup" aria-label="Empezar con">
          <label v-for="[clave, nombres] in PLANTILLAS_LISTAS" :key="clave">
            <input v-model="plantilla" type="radio" name="plantilla" :value="clave" />{{ nombres.join(" · ") }}
          </label>
          <label v-if="copiables.length">
            <input v-model="plantilla" type="radio" name="plantilla" value="copiar" />Las listas de otra pizarra
          </label>
          <select
            v-if="plantilla === 'copiar'"
            v-model="copiarDe"
            aria-label="Pizarra de la que se copian las listas"
            class="copiar-de"
          >
            <option v-for="p in copiables" :key="p.id" :value="p.id">{{ p.nombre }}</option>
          </select>
          <label><input v-model="plantilla" type="radio" name="plantilla" value="vacia" />Sin listas</label>
        </div>
        <div v-if="errorPlantilla" class="error">{{ errorPlantilla }}</div>
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
