<!--
  Una actividad en una sola vista (§5, 2026-10-20): al abrirla, quien tiene «Editar» ve el
  formulario con todo («Eliminar» y «Viene de» arriba; comentarios e historial abajo, en
  `LineaTiempo`), sin pasar por un detalle
  aparte. Modos:
  - editar: alta (con `actividadId` null, en `listaInicial`; arriba con `arriba`) o edición;
  - ver: solo lectura, para quien no tiene «Editar» (o la pizarra está archivada);
  - convertir: alta de una actividad enlazada a un elemento de la checklist (§4.6). Cuándo se
    palomea solo lo dice la checklist de la actividad original («Lo que llega a … cuenta como
    terminado»), no cada conversión.
  Alta, edición y conversión usan los mismos campos (Etapa 3.8, §4.7). Los campos se guardan con
  «Guardar»; la lista (un toque la mueve arriba), la checklist y los adjuntos de una actividad que
  ya existe se guardan al momento. Cerrar o convertir con cambios sin guardar pregunta antes.
  Lo que el usuario no puede hacer no se muestra o queda deshabilitado según los permisos que le
  dio el dueño (pizarra.permisos; todo en falso si la pizarra está archivada).
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { tamanoLegible, prepararArchivo } from "../adjuntos";
import { api, ErrorApi, mensajeDeError, subir } from "../api";
import { sesion } from "../sesion";
import type { Actividad, EleccionSolicitante, ElementoChecklist, PizarraDetalle } from "../tipos";
import { avisar, confirmar } from "../ui";
import { fechaHora, fechaLarga, MAX_TEXTO_ELEMENTO, partirTitulo } from "../utilidades";
import Adjuntos from "./Adjuntos.vue";
import Avatar from "./Avatar.vue";
import Checklist from "./Checklist.vue";
import Chips from "./Chips.vue";
import ElegirSolicitante from "./ElegirSolicitante.vue";
import Hoja from "./Hoja.vue";
import Icono from "./Icono.vue";
import LineaTiempo from "./LineaTiempo.vue";

const props = defineProps<{
  pizarra: PizarraDetalle;
  actividadId: number | null;
  listaInicial?: number;
  arriba?: boolean;
}>();
const emit = defineEmits<{
  cerrar: [];
  guardada: [t: Actividad];
  eliminada: [id: number];
  /** Abrir otra actividad (la de origen o una creada desde la checklist). */
  abrir: [id: number];
}>();

const actividad = ref<Actividad | null>(null);
const modo = ref<"ver" | "editar" | "convertir">("editar");
const elemento = ref<ElementoChecklist | null>(null);
const cargando = ref(!!props.actividadId);
const ocupado = ref(false);
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");

const p = computed(() => props.pizarra);
const puede = computed(() => p.value.permisos);
const tiposDe = computed(() => p.value.tipos.filter((tp) => actividad.value?.tipos.includes(tp.id)));
const faltanPermisos = computed(() => !puede.value.mover || !puede.value.editar || !puede.value.eliminar);
/** Lo que se ve de una actividad que ya existe: su formulario o, sin «Editar», solo lectura. */
const modoBase = computed(() => (puede.value.editar ? "editar" : "ver"));
/** Una actividad que ya existe, en su formulario (no en el alta ni al convertir). */
const editando = computed(() => modo.value === "editar" && !!actividad.value);

const form = reactive({
  titulo: "",
  descripcion: "",
  lista: 0,
  fecha_solicitud: "",
  fecha_fin: "",
  tipos: [] as number[],
  asignados: [] as number[],
  /** Solo al crear: los textos de la checklist, que se guardan con la actividad. */
  checklist: [] as string[],
  lista_al_completar: null as number | null,
  solicitante: null as EleccionSolicitante | null,
});
const nuevoElemento = ref("");
/** Solo al crear: los archivos elegidos, que se suben después de crear la actividad. */
const archivosNuevos = ref<File[]>([]);
const entradaArchivos = ref<HTMLInputElement>();
const editandoLocal = ref<number | null>(null);
const vEnfocar = { mounted: (el: HTMLElement) => el.focus() };

/** El formulario como quedó al llenarlo; si cambia, hay algo sin guardar. */
const huella = () =>
  JSON.stringify({
    ...form,
    // En una actividad que ya existe, la lista se cambia al momento, no con «Guardar».
    lista: editando.value ? 0 : form.lista,
    archivos: archivosNuevos.value.length,
    nuevo: nuevoElemento.value.trim(),
  });
const huellaGuardada = ref("");
const hayCambios = computed(() => huella() !== huellaGuardada.value);
/** Comentario escrito y sin publicar: no lo guarda «Guardar», pero cerrar pregunta (2026-10-20). */
const borradorComentario = ref("");
const sinGuardar = computed(() => hayCambios.value || !!borradorComentario.value.trim());

function llenarForm(t: Actividad | null) {
  form.titulo = t?.titulo ?? "";
  form.descripcion = t?.descripcion ?? "";
  form.lista = t?.lista ?? props.listaInicial ?? p.value.listas[0]?.id ?? 0;
  form.fecha_solicitud = t?.fecha_solicitud ?? "";
  form.fecha_fin = t?.fecha_fin ?? "";
  form.tipos = [...(t?.tipos ?? [])];
  form.asignados = (t?.asignados ?? []).map((u) => u.id);
  form.checklist = [];
  form.lista_al_completar = t?.lista_al_completar ?? null;
  form.solicitante = t?.solicitante ? { ...t.solicitante } : null;
  nuevoElemento.value = "";
  editandoLocal.value = null;
  archivosNuevos.value = [];
  errores.value = {};
  errorGeneral.value = "";
  huellaGuardada.value = huella();
}

async function cargar() {
  if (!props.actividadId) {
    llenarForm(null);
    return;
  }
  cargando.value = true;
  try {
    actividad.value = await api<Actividad>(`actividades/${props.actividadId}/`);
    modo.value = modoBase.value;
    llenarForm(actividad.value);
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudo abrir la actividad."));
    emit("cerrar");
  } finally {
    cargando.value = false;
  }
}
watch(() => props.actividadId, cargar, { immediate: true });

const descartar = () => confirmar("Hay cambios sin guardar. ¿Descartarlos?", "Descartar");

/** Formulario de actividad nueva, prellenado con el elemento y enlazado a él (§4.6). */
async function convertir(e: ElementoChecklist) {
  const t = actividad.value!;
  if (sinGuardar.value && !(await descartar())) return;
  borradorComentario.value = "";
  llenarForm(null);
  // Los elementos llegan a 400 caracteres y el título a 200: el resto va a la descripción.
  [form.titulo, form.descripcion] = partirTitulo(e.texto);
  form.lista = t.lista;
  form.asignados = t.asignados.map((u) => u.id);
  elemento.value = e;
  modo.value = "convertir";
  huellaGuardada.value = huella();
}

/** Vuelve a la actividad original (después de convertir o al cancelar la conversión). */
function volverAOriginal() {
  elemento.value = null;
  modo.value = modoBase.value;
  llenarForm(actividad.value);
}

/** Formulario de alta: agrega a la checklist local (Enter no envía el formulario). */
function agregarElemento() {
  const texto = nuevoElemento.value.trim();
  if (!texto) return;
  form.checklist.push(texto);
  nuevoElemento.value = "";
}

function elegirArchivos(ev: Event) {
  const entrada = ev.target as HTMLInputElement;
  archivosNuevos.value.push(...(entrada.files ?? []));
  entrada.value = "";
}

/** Después de crear: sube los archivos del formulario. Devuelve la actividad con ellos. */
async function subirArchivosNuevos(t: Actividad): Promise<Actividad> {
  const fallidos: string[] = [];
  for (const original of archivosNuevos.value) {
    const archivo = await prepararArchivo(original);
    const datos = new FormData();
    datos.append("archivo", archivo);
    try {
      t = await subir<Actividad>(`actividades/${t.id}/adjuntos/`, datos);
    } catch (e) {
      fallidos.push(`«${original.name}»: ${mensajeDeError(e)}`);
    }
  }
  archivosNuevos.value = [];
  if (fallidos.length) avisar(`No se adjuntó ${fallidos.join(" ")}`);
  return t;
}

/** Formulario de alta: el texto de un elemento se corrige tocándolo; vacío, se quita. */
function guardarLocal(i: number, ev: Event) {
  if (editandoLocal.value !== i) return;
  const texto = (ev.target as HTMLTextAreaElement).value.trim();
  if (texto) form.checklist[i] = texto;
  else form.checklist.splice(i, 1);
  editandoLocal.value = null;
}

function datosForm() {
  const { solicitante, ...resto } = form;
  return {
    ...resto,
    // Una sola persona (§4.4): los tres campos van siempre, para que editar reemplace al anterior.
    solicitada_por: solicitante?.tipo === "miembro" ? solicitante.id : null,
    solicitante_externo: solicitante?.tipo === "externo" ? solicitante.id : null,
    solicitante_nuevo: solicitante?.tipo === "nuevo" ? solicitante.nombre : "",
    titulo: form.titulo.trim(),
    fecha_solicitud: form.fecha_solicitud || null,
    fecha_fin: form.fecha_fin || null,
  };
}

async function guardar() {
  errores.value = {};
  errorGeneral.value = "";
  if (!form.titulo.trim()) {
    errores.value = { titulo: "Escribe un título." };
    return;
  }
  ocupado.value = true;
  try {
    const { checklist, lista_al_completar, ...todos } = datosForm();
    // En una actividad que ya existe, la lista y «Al completar» se guardan al momento (no se
    // pisan con el valor del formulario).
    const { lista, ...sinLista } = todos;
    const datos = editando.value ? sinLista : { ...todos, lista, lista_al_completar };
    if (modo.value === "convertir" && elemento.value) {
      const r = await api<{ actividad: Actividad; nueva: Actividad }>(`checklist/${elemento.value.id}/convertir/`, "POST", {
        ...datos,
        checklist,
      });
      actividad.value = r.actividad;
      volverAOriginal();
      avisar("Se creó la actividad desde la checklist.");
      emit("guardada", archivosNuevos.value.length ? await subirArchivosNuevos(r.nueva) : r.nueva);
      return;
    }
    const t = actividad.value
      ? await api<Actividad>(`actividades/${actividad.value.id}/`, "PATCH", datos)
      : await api<Actividad>(`pizarras/${p.value.id}/actividades/`, "POST", {
          ...datos,
          checklist,
          arriba: !!props.arriba,
        });
    const nueva = !actividad.value;
    avisar(nueva ? "Se creó la actividad." : "Se guardaron los cambios.");
    actividad.value = nueva && archivosNuevos.value.length ? await subirArchivosNuevos(t) : t;
    llenarForm(actividad.value);
    emit("guardada", actividad.value);
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

/** Cambiar de lista con un toque: queda arriba (2026-10-20; el orden se cambia arrastrando). */
async function moverA(listaId: number) {
  const t = actividad.value;
  if (!t || t.lista === listaId || ocupado.value) return;
  ocupado.value = true;
  try {
    actividad.value = await api<Actividad>(`actividades/${t.id}/mover/`, "POST", { lista: listaId });
    form.lista = listaId;
    emit("guardada", actividad.value);
    avisar(`Se movió a «${actividad.value.lista_nombre}».`);
  } catch (e) {
    avisar(mensajeDeError(e));
  } finally {
    ocupado.value = false;
  }
}

/** «Cumplida» (2026-10-20): se guarda al momento, sin tocar lo que haya sin guardar en el formulario. */
async function alternarCumplida(ev: Event) {
  const t = actividad.value;
  const casilla = ev.target as HTMLInputElement;
  if (!t) return;
  ocupado.value = true;
  try {
    actividad.value = await api<Actividad>(`actividades/${t.id}/cumplida/`, "POST", { cumplida: casilla.checked });
    emit("guardada", actividad.value);
    avisar(casilla.checked ? "Se marcó como cumplida." : "Se volvió a abrir.");
  } catch (e) {
    casilla.checked = !casilla.checked;
    avisar(mensajeDeError(e));
  } finally {
    ocupado.value = false;
  }
}

function checklistActualizada(t: Actividad) {
  actividad.value = t;
  emit("guardada", t);
}

async function eliminar() {
  const t = actividad.value;
  if (!t) return;
  const ok = await confirmar(`¿Eliminar la actividad «${t.titulo}»? Esta acción no se puede deshacer.`, "Eliminar");
  if (!ok) return;
  try {
    await api(`actividades/${t.id}/`, "DELETE");
    avisar("Se eliminó la actividad.");
    emit("eliminada", t.id);
    emit("cerrar");
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

/** Cerrar (o «Cancelar»): al convertir, regresa a la original; con cambios, pregunta antes. */
async function cerrar() {
  if (sinGuardar.value && !(await descartar())) return;
  if (modo.value === "convertir") volverAOriginal();
  else emit("cerrar");
}

const esYo = (id: number | undefined) => id === sesion.usuario?.id;
const titulo = computed(() => {
  if (modo.value === "convertir") return "Nueva actividad";
  return actividad.value?.titulo ?? "Nueva actividad";
});
</script>

<template>
  <Hoja :titulo="titulo" @cerrar="cerrar">
    <div v-if="cargando" class="cargando" style="min-height: 120px">Cargando…</div>

    <template v-else>
      <!-- De una actividad que ya existe (no al convertir). «Eliminar» arriba y no al final: el
           historial crece y lo dejaría cada vez más lejos (2026-10-06). -->
      <template v-if="actividad && modo !== 'convertir'">
        <div v-if="puede.eliminar" class="acciones-detalle">
          <button type="button" class="btn btn-chico btn-peligro" @click="eliminar">
            <Icono nombre="basura" />Eliminar
          </button>
        </div>
        <div v-if="actividad.viene_de" class="viene-de">
          <Icono nombre="enlace" />
          <span
            >Viene de la checklist de
            <button type="button" @click="emit('abrir', actividad.viene_de.id)">{{ actividad.viene_de.titulo }}</button></span
          >
        </div>
        <!-- Un toque la mueve arriba de la lista (§4.6, 2026-10-20), sin esperar a «Guardar». -->
        <div class="campo">
          <span class="etiqueta">Lista</span>
          <div v-if="puede.mover" class="elegir-lista" role="radiogroup" aria-label="Mover a la lista">
            <button
              v-for="l in p.listas"
              :key="l.id"
              type="button"
              role="radio"
              :aria-checked="actividad.lista === l.id"
              :disabled="ocupado"
              @click="moverA(l.id)"
            >
              <Icono v-if="actividad.lista === l.id" nombre="palomita" />{{ l.nombre }}
            </button>
          </div>
          <Chips v-else :lista="actividad.lista_nombre" />
        </div>
      </template>

    <!-- Solo lectura: sin permiso «Editar» o pizarra archivada -->
    <template v-if="modo === 'ver' && actividad">
      <div class="campo">
        <span class="etiqueta">Solicitada por</span>
        <span v-if="actividad.solicitante" class="persona-texto">{{ actividad.solicitante.nombre }}</span>
        <span v-else class="ayuda" style="font-size: 14px">Sin solicitante</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Tipos</span>
        <div v-if="tiposDe.length" class="tipos-actividad"><Chips v-for="tp in tiposDe" :key="tp.id" :tipo="tp" /></div>
        <span v-else class="ayuda" style="font-size: 14px">Sin tipo</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Descripción</span>
        <p v-if="actividad.descripcion" class="texto-largo">{{ actividad.descripcion }}</p>
        <span v-else class="ayuda" style="font-size: 14px">Sin descripción</span>
      </div>
      <div class="dos-campos">
        <div class="campo">
          <span class="etiqueta">Solicitada el</span>
          <span v-if="actividad.fecha_solicitud" class="chip fecha"
            ><Icono nombre="calendario" />{{ fechaLarga(actividad.fecha_solicitud) }}</span
          >
          <span v-else class="ayuda" style="font-size: 14px">Sin fecha</span>
        </div>
        <div class="campo">
          <span class="etiqueta">Vence el</span>
          <Chips v-if="actividad.fecha_fin" :fecha="actividad" />
          <span v-else class="ayuda" style="font-size: 14px">Sin fecha</span>
        </div>
      </div>
      <Checklist
        :actividad="actividad"
        :pizarra="p"
        @actualizada="checklistActualizada"
        @convertir="convertir"
        @abrir="(id) => emit('abrir', id)"
      />
      <Adjuntos :actividad="actividad" :pizarra="p" @actualizada="checklistActualizada" />
      <div class="campo">
        <span class="etiqueta">Asignada a · {{ actividad.asignados.length }}</span>
        <div class="personas">
          <div v-for="u in actividad.asignados" :key="u.id" class="persona">
            <Avatar :usuario="u" />
            <div class="nombre">{{ u.nombre }}{{ esYo(u.id) ? " (tú)" : "" }}</div>
          </div>
          <span v-if="!actividad.asignados.length" class="ayuda" style="font-size: 14px">Sin asignar</span>
        </div>
      </div>
    </template>

    <!-- Alta / edición / conversión: los mismos campos (Etapa 3.8, §4.7) -->
    <form v-else novalidate @submit.prevent="guardar">
      <div v-if="modo === 'convertir' && actividad" class="viene-de">
        <Icono nombre="enlace" />
        <span>Desde la checklist de <b>{{ actividad.titulo }}</b>. Quedarán enlazadas.</span>
      </div>
      <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
      <div class="campo">
        <label for="f-titulo">Título <span class="obligatorio" aria-hidden="true">*</span></label>
        <input
          id="f-titulo"
          v-model="form.titulo"
          type="text"
          maxlength="200"
          placeholder="¿Qué hay que hacer?"
          aria-required="true"
        />
        <div v-if="errores.titulo" class="error">{{ errores.titulo }}</div>
      </div>
      <!-- Al crear o convertir; en una que ya existe, la lista va arriba con sus botones. -->
      <div v-if="!editando" class="campo">
        <label for="f-lista">Lista <span class="obligatorio" aria-hidden="true">*</span></label>
        <select id="f-lista" v-model="form.lista" aria-required="true">
          <option v-for="l in p.listas" :key="l.id" :value="l.id">{{ l.nombre }}</option>
        </select>
        <div v-if="errores.lista" class="error">{{ errores.lista }}</div>
      </div>
      <div class="campo">
        <label for="f-desc">Descripción</label>
        <textarea id="f-desc" v-model="form.descripcion" placeholder="Detalles, criterios de terminado…" />
      </div>
      <div class="campo">
        <label for="f-solicitante">Solicitada por</label>
        <ElegirSolicitante id="f-solicitante" v-model="form.solicitante" :pizarra="p" />
        <div v-if="errores.solicitante" class="error">{{ errores.solicitante }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Tipos</span>
        <div v-if="p.tipos.length" class="elegir-tipos">
          <label v-for="tp in p.tipos" :key="tp.id">
            <input v-model="form.tipos" type="checkbox" :value="tp.id" />
            <span class="chip tipo" :style="{ '--tipo': tp.color }"><span class="punto" />{{ tp.nombre }}</span>
          </label>
        </div>
        <div v-else class="ayuda">Esta pizarra aún no tiene tipos.</div>
        <div v-if="errores.tipos" class="error">{{ errores.tipos }}</div>
      </div>
      <div class="dos-campos">
        <div class="campo">
          <label for="f-solicitud">Solicitada el</label>
          <input id="f-solicitud" v-model="form.fecha_solicitud" type="date" />
          <div v-if="errores.fecha_solicitud" class="error">{{ errores.fecha_solicitud }}</div>
        </div>
        <div class="campo">
          <label for="f-fecha">Vence el</label>
          <input id="f-fecha" v-model="form.fecha_fin" type="date" />
          <div v-if="errores.fecha_fin" class="error">{{ errores.fecha_fin }}</div>
          <!-- «Cumplida» (2026-10-20): solo con fecha de vencimiento ya guardada; al momento. -->
          <div v-if="editando && actividad?.fecha_fin" class="marcar-cumplida">
            <label>
              <input type="checkbox" :checked="!!actividad.cumplida_en" :disabled="ocupado" @change="alternarCumplida" />
              Cumplida
            </label>
            <small v-if="actividad.cumplida_en" class="ayuda"
              >{{ actividad.cumplida_por?.nombre ?? "Usuario eliminado" }} · {{ fechaHora(actividad.cumplida_en) }}</small
            >
          </div>
        </div>
      </div>
      <div class="campo">
        <span class="etiqueta">Asignar a</span>
        <div class="personas">
          <label v-for="m in p.miembros" :key="m.usuario.id" class="persona">
            <input v-model="form.asignados" type="checkbox" :value="m.usuario.id" />
            <Avatar :usuario="m.usuario" />
            <span class="nombre">{{ m.usuario.nombre }}{{ esYo(m.usuario.id) ? " (tú)" : "" }}</span>
          </label>
        </div>
        <div v-if="errores.asignados" class="error">{{ errores.asignados }}</div>
      </div>
      <!-- Editar: la checklist de la actividad, que se guarda al momento. Convertir un elemento
           cambia el formulario por el de la actividad nueva (pregunta si hay cambios sin guardar). -->
      <Checklist
        v-if="editando && actividad"
        :actividad="actividad"
        :pizarra="p"
        @actualizada="checklistActualizada"
        @convertir="convertir"
        @abrir="(id) => emit('abrir', id)"
      />
      <!-- Crear o convertir: la checklist se junta aquí y se guarda con la actividad. -->
      <div v-else class="campo">
        <div class="checklist-cab">
          <span class="etiqueta">Checklist<template v-if="form.checklist.length"> · {{ form.checklist.length }}</template></span>
          <label v-if="form.checklist.length" class="al-completar">
            Al completar, mover a
            <select v-model="form.lista_al_completar">
              <option :value="null">ninguna</option>
              <option v-for="l in p.listas.filter((x) => x.id !== form.lista)" :key="l.id" :value="l.id">{{ l.nombre }}</option>
            </select>
          </label>
        </div>
        <ul v-if="form.checklist.length" class="checklist">
          <li v-for="(texto, i) in form.checklist" :key="i">
            <div class="elemento">
              <input type="checkbox" disabled :aria-label="texto" />
              <textarea
                v-if="editandoLocal === i"
                v-enfocar
                class="editar-texto"
                rows="2"
                :value="texto"
                :maxlength="MAX_TEXTO_ELEMENTO"
                aria-label="Texto del elemento"
                @keydown.enter.prevent="guardarLocal(i, $event)"
                @keydown.esc.stop.prevent="editandoLocal = null"
                @blur="guardarLocal(i, $event)"
              />
              <span
                v-else
                class="texto editable"
                role="button"
                tabindex="0"
                :title="`Editar «${texto}»`"
                @click="editandoLocal = i"
                @keydown.enter.prevent="editandoLocal = i"
                >{{ texto }}</span
              >
            </div>
            <button
              type="button"
              class="btn-icono"
              :aria-label="`Quitar «${texto}»`"
              title="Quitar"
              @click="form.checklist.splice(i, 1)"
            >
              <Icono nombre="cerrarChico" />
            </button>
          </li>
        </ul>
        <div class="agregar-item">
          <input
            v-model="nuevoElemento"
            type="text"
            :maxlength="MAX_TEXTO_ELEMENTO"
            placeholder="Agregar elemento"
            aria-label="Agregar elemento a la checklist"
            @keydown.enter.prevent="agregarElemento"
          />
          <button type="button" class="btn btn-chico btn-secundario" :disabled="!nuevoElemento.trim()" @click="agregarElemento">
            Agregar
          </button>
        </div>
        <div v-if="errores.texto" class="error">{{ errores.texto }}</div>
      </div>
      <!-- Editar: los adjuntos se guardan al momento; crear: se suben después de crear la actividad. -->
      <Adjuntos v-if="editando && actividad" :actividad="actividad" :pizarra="p" @actualizada="checklistActualizada" />
      <div v-else class="campo">
        <span class="etiqueta">Adjuntos<template v-if="archivosNuevos.length"> · {{ archivosNuevos.length }}</template></span>
        <ul v-if="archivosNuevos.length" class="adjuntos">
          <li v-for="(f, i) in archivosNuevos" :key="i">
            <Icono nombre="clip" />
            <span class="nombre-archivo">{{ f.name }}</span>
            <small>{{ tamanoLegible(f.size) }}</small>
            <button
              type="button"
              class="btn-icono"
              :aria-label="`Quitar «${f.name}»`"
              title="Quitar"
              @click="archivosNuevos.splice(i, 1)"
            >
              <Icono nombre="cerrarChico" />
            </button>
          </li>
        </ul>
        <input ref="entradaArchivos" type="file" multiple hidden @change="elegirArchivos" />
        <button type="button" class="btn btn-chico btn-secundario" @click="entradaArchivos?.click()">
          <Icono nombre="clip" /> Adjuntar archivos
        </button>
      </div>
      <!-- Fija al pie de la hoja: con checklist, adjuntos e historial, «Guardar» quedaba lejos. -->
      <div class="fila-botones fija">
        <button type="button" class="btn btn-secundario" @click="cerrar">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado || (editando && !hayCambios)">
          {{ ocupado ? "Guardando…" : "Guardar" }}
        </button>
      </div>
    </form>

      <!-- De una actividad que ya existe, debajo de sus campos (no al convertir). -->
      <template v-if="actividad && modo !== 'convertir'">
        <!-- Comentarios e historial en una sola línea de tiempo (2026-10-20). -->
        <LineaTiempo
          v-model:borrador="borradorComentario"
          :actividad="actividad"
          :pizarra="p"
          @actualizada="checklistActualizada"
        />
        <!-- Sin «Pizarra: …» ni «Creada por … el …» (Etapa 3.8): el historial ya dice quién y cuándo. -->
        <div v-if="p.archivada || (faltanPermisos && p.dueno)" class="meta">
          <span v-if="p.archivada">Pizarra archivada: solo lectura.</span>
          <span v-else-if="p.dueno"
            >Lo que no ves disponible depende de los permisos que te dio el dueño ({{ p.dueno.nombre }}).</span
          >
        </div>
      </template>
    </template>
  </Hoja>
</template>
