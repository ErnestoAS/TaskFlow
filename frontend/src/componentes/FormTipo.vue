<script setup lang="ts">
import { reactive, ref } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import type { Tipo } from "../tipos";
import { avisar } from "../ui";
import { MUESTRAS } from "../utilidades";
import Chips from "./Chips.vue";
import Hoja from "./Hoja.vue";

const props = defineProps<{ proyectoId: number; tipo: Tipo | null; sugerido: string }>();
const emit = defineEmits<{ cerrar: []; guardado: [] }>();

const form = reactive({
  nombre: props.tipo?.nombre ?? "",
  descripcion: props.tipo?.descripcion ?? "",
  color: props.tipo?.color ?? props.sugerido,
});
const errores = ref<Record<string, string>>({});
const ocupado = ref(false);

async function guardar() {
  errores.value = {};
  if (!form.nombre.trim()) {
    errores.value = { nombre: "Escribe un nombre." };
    return;
  }
  ocupado.value = true;
  const datos = { ...form, nombre: form.nombre.trim() };
  try {
    if (props.tipo) await api(`proyectos/${props.proyectoId}/tipos/${props.tipo.id}/`, "PATCH", datos);
    else await api(`proyectos/${props.proyectoId}/tipos/`, "POST", datos);
    avisar(props.tipo ? "Se guardó el tipo." : "Se creó el tipo.");
    emit("guardado");
  } catch (e) {
    errores.value =
      e instanceof ErrorApi && Object.keys(e.campos).length ? e.campos : { nombre: mensajeDeError(e) };
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <Hoja :titulo="tipo ? 'Editar tipo' : 'Nuevo tipo de tarjeta'" @cerrar="emit('cerrar')">
    <form novalidate @submit.prevent="guardar">
      <div class="campo">
        <label for="f-tnombre">Nombre</label>
        <input id="f-tnombre" v-model="form.nombre" type="text" maxlength="50" placeholder="Ej. Difusión" />
        <div v-if="errores.nombre" class="error">{{ errores.nombre }}</div>
      </div>
      <div class="campo">
        <label for="f-tdesc">Descripción <span style="text-transform: none; font-weight: 400">(opcional)</span></label>
        <textarea id="f-tdesc" v-model="form.descripcion" style="min-height: 70px" placeholder="Para qué tarjetas se usa" />
      </div>
      <div class="campo">
        <span class="etiqueta">Color</span>
        <div class="muestras" role="group" aria-label="Colores sugeridos">
          <button
            v-for="m in MUESTRAS"
            :key="m"
            type="button"
            :style="{ '--tipo': m }"
            :aria-pressed="form.color.toLowerCase() === m"
            :aria-label="`Color ${m}`"
            @click="form.color = m"
          />
          <input v-model="form.color" type="color" aria-label="Otro color" />
        </div>
        <div class="ayuda">Elige uno sugerido u otro con el selector.</div>
        <div v-if="errores.color" class="error">{{ errores.color }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Vista previa</span>
        <Chips :tipo="{ id: 0, nombre: form.nombre || 'Nombre del tipo', descripcion: '', color: form.color }" />
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="emit('cerrar')">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">Guardar</button>
      </div>
    </form>
  </Hoja>
</template>
