<!--
  Adjuntos de una actividad (Etapa 3.8, §4.4), en el detalle y en el formulario de edición: se
  guardan al momento. Abrir o descargar, cualquier miembro (imágenes y PDF se abren; lo demás se
  descarga, §7); adjuntar y quitar, permiso «Editar». Las fotos se reducen antes de subir.
-->
<script setup lang="ts">
import { computed, ref } from "vue";

import { tamanoLegible, prepararArchivo } from "../adjuntos";
import { ErrorApi, mensajeDeError, rutaApi, subir, api } from "../api";
import type { Actividad, Adjunto, PizarraDetalle } from "../tipos";
import { avisar, confirmar } from "../ui";
import Icono from "./Icono.vue";

const props = defineProps<{ actividad: Actividad; pizarra: PizarraDetalle }>();
const emit = defineEmits<{ actualizada: [t: Actividad] }>();

const lista = computed<Adjunto[]>(() => props.actividad.adjuntos ?? []);
const puedeEditar = computed(() => props.pizarra.permisos.editar);
const subiendo = ref("");
const error = ref("");
const entrada = ref<HTMLInputElement>();

async function alElegir(ev: Event) {
  const archivos = [...((ev.target as HTMLInputElement).files ?? [])];
  (ev.target as HTMLInputElement).value = "";
  error.value = "";
  const maximo = props.pizarra.adjuntos_espacio.max_archivo;
  let subidos = 0;
  for (const original of archivos) {
    subiendo.value = original.name;
    const archivo = await prepararArchivo(original);
    if (archivo.size > maximo) {
      error.value = `«${original.name}» pasa de ${tamanoLegible(maximo)}.`;
      continue;
    }
    const datos = new FormData();
    datos.append("archivo", archivo);
    try {
      emit("actualizada", await subir<Actividad>(`actividades/${props.actividad.id}/adjuntos/`, datos));
      subidos++;
    } catch (e) {
      error.value = e instanceof ErrorApi ? (e.campos.archivo ?? e.message) : mensajeDeError(e);
    }
  }
  subiendo.value = "";
  if (subidos) avisar(subidos === 1 ? "Se adjuntó el archivo." : `Se adjuntaron ${subidos} archivos.`);
}

async function quitar(a: Adjunto) {
  if (!(await confirmar(`¿Quitar «${a.nombre}»? El archivo se borra y no se puede recuperar.`, "Quitar"))) return;
  try {
    emit("actualizada", await api<Actividad>(`adjuntos/${a.id}/`, "DELETE"));
    avisar("Se quitó el archivo.");
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}
</script>

<template>
  <div class="campo">
    <span class="etiqueta">Adjuntos<template v-if="lista.length"> · {{ lista.length }}</template></span>
    <ul v-if="lista.length" class="adjuntos">
      <li v-for="a in lista" :key="a.id">
        <Icono nombre="clip" />
        <a :href="rutaApi(`adjuntos/${a.id}/`)" target="_blank" rel="noopener">{{ a.nombre }}</a>
        <small>{{ tamanoLegible(a.tamano) }}</small>
        <button
          v-if="puedeEditar"
          type="button"
          class="btn-icono"
          :aria-label="`Quitar «${a.nombre}»`"
          title="Quitar"
          @click="quitar(a)"
        >
          <Icono nombre="cerrarChico" />
        </button>
      </li>
    </ul>
    <span v-else-if="!puedeEditar" class="ayuda" style="font-size: 14px">Sin adjuntos</span>
    <template v-if="puedeEditar">
      <input ref="entrada" type="file" multiple hidden @change="alElegir" />
      <button type="button" class="btn btn-chico btn-secundario" :disabled="!!subiendo" @click="entrada?.click()">
        <Icono nombre="clip" /> {{ subiendo ? `Subiendo «${subiendo}»…` : "Adjuntar archivos" }}
      </button>
    </template>
    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>
