<!--
  Combo «Solicitada por» (Etapa 3.8, §4.7): busca entre los miembros de la pizarra y los
  solicitantes externos de su catálogo; si lo escrito no existe, ofrece «Agregar «…»», que se crea
  al guardar la actividad. Con teclado: flechas, Enter elige, Esc cierra. El ✕ deja la actividad
  sin solicitante. Un miembro que ya era el solicitante y salió de la pizarra sigue apareciendo.
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";

import type { EleccionSolicitante, PizarraDetalle } from "../tipos";
import Icono from "./Icono.vue";

const props = defineProps<{ pizarra: PizarraDetalle; modelValue: EleccionSolicitante | null; id?: string }>();
const emit = defineEmits<{ "update:modelValue": [v: EleccionSolicitante | null] }>();

const idLista = `${props.id ?? "solicitante"}-opciones`;
const texto = ref(props.modelValue?.nombre ?? "");
const abierto = ref(false);
const activa = ref(0);
watch(
  () => props.modelValue,
  (v) => (texto.value = v?.nombre ?? ""),
);

/** Sin mayúsculas ni acentos: «perez» encuentra a «Pérez». */
const normal = (s: string) =>
  s
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLowerCase()
    .replace(/\s+/g, " ")
    .trim();

const conocidos = computed<EleccionSolicitante[]>(() => {
  const miembros: EleccionSolicitante[] = props.pizarra.miembros.map((m) => ({
    tipo: "miembro",
    id: m.usuario.id,
    nombre: m.usuario.nombre,
  }));
  const v = props.modelValue;
  if (v?.tipo === "miembro" && !miembros.some((m) => m.id === v.id)) miembros.push(v);
  const externos: EleccionSolicitante[] = (props.pizarra.solicitantes ?? []).map((s) => ({
    tipo: "externo",
    id: s.id,
    nombre: s.nombre,
  }));
  return [...miembros, ...externos];
});

const opciones = computed<EleccionSolicitante[]>(() => {
  // Con el nombre elegido a la vista se muestran todos; al escribir, se filtra.
  const escrito = texto.value.replace(/\s+/g, " ").trim();
  const q = escrito === (props.modelValue?.nombre ?? "") ? "" : normal(escrito);
  const lista = conocidos.value.filter((o) => !q || normal(o.nombre).includes(q));
  if (q && !conocidos.value.some((o) => normal(o.nombre) === q)) lista.push({ tipo: "nuevo", nombre: escrito });
  return lista;
});

const grupo = (i: number) => {
  const o = opciones.value[i];
  if (o.tipo === "nuevo" || (i > 0 && opciones.value[i - 1].tipo === o.tipo)) return "";
  return o.tipo === "miembro" ? "Miembros de la pizarra" : "Otras personas";
};

function abrir() {
  abierto.value = true;
  activa.value = 0;
}

function elegir(o: EleccionSolicitante | undefined) {
  if (!o) return;
  emit("update:modelValue", o);
  texto.value = o.nombre;
  abierto.value = false;
}

function quitar() {
  emit("update:modelValue", null);
  texto.value = "";
  abierto.value = false;
}

/** Al salir sin elegir, vuelve lo que estaba (borrar el texto no quita: para eso es el ✕). */
function alSalir() {
  abierto.value = false;
  texto.value = props.modelValue?.nombre ?? "";
}

function moverActiva(paso: number) {
  if (!abierto.value) return abrir();
  const n = opciones.value.length;
  if (n) activa.value = (activa.value + paso + n) % n;
}
</script>

<template>
  <div class="combo">
    <input
      :id="id"
      v-model="texto"
      type="text"
      role="combobox"
      autocomplete="off"
      maxlength="100"
      placeholder="Busca o escribe un nombre"
      aria-autocomplete="list"
      :aria-expanded="abierto"
      :aria-controls="idLista"
      :aria-activedescendant="abierto && opciones.length ? `${idLista}-${activa}` : undefined"
      @focus="abrir"
      @input="(abierto = true), (activa = 0)"
      @keydown.down.prevent="moverActiva(1)"
      @keydown.up.prevent="moverActiva(-1)"
      @keydown.enter.prevent="abierto ? elegir(opciones[activa]) : abrir()"
      @keydown.esc="abierto && ($event.stopPropagation(), alSalir())"
      @blur="alSalir"
    />
    <button
      v-if="modelValue"
      type="button"
      class="btn-icono"
      aria-label="Quitar solicitante"
      title="Sin solicitante"
      @mousedown.prevent
      @click="quitar"
    >
      <Icono nombre="cerrarChico" />
    </button>
    <ul v-if="abierto && opciones.length" :id="idLista" role="listbox" class="combo-lista">
      <template v-for="(o, i) in opciones" :key="`${o.tipo}-${o.id ?? o.nombre}`">
        <li v-if="grupo(i)" class="combo-grupo" role="presentation">{{ grupo(i) }}</li>
        <li
          :id="`${idLista}-${i}`"
          role="option"
          class="combo-opcion"
          :class="{ activa: i === activa, nuevo: o.tipo === 'nuevo' }"
          :aria-selected="i === activa"
          @mousedown.prevent="elegir(o)"
          @mousemove="activa = i"
        >
          <template v-if="o.tipo === 'nuevo'"><Icono nombre="masChico" /> Agregar «{{ o.nombre }}»</template>
          <template v-else>{{ o.nombre }}</template>
        </li>
      </template>
    </ul>
  </div>
</template>
