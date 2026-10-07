<!--
  Detalle de una actividad y su formulario, en la misma hoja (§5). Modos:
  - ver: lista (cambiarla con un toque), tipos, descripción, fechas, checklist,
    asignados e historial; «Viene de» si nació de la checklist de otra actividad;
  - editar: alta (con `actividadId` null, en `listaInicial`; arriba con `arriba`) o edición;
  - convertir: alta de una actividad enlazada a un elemento de la checklist (§4.6). Cuándo se
    palomea solo lo dice la checklist de la actividad original («Lo que llega a … cuenta como
    terminado»), no cada conversión.
  Alta, edición y conversión usan el mismo formulario con los mismos campos (Etapa 3.8, §4.7). Al
  crear, la checklist se junta en el formulario y va con la actividad; al editar, se guarda al
  momento, como en el detalle. Cambiar la lista al editar la mueve al final de la nueva.
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
const modo = ref<"ver" | "editar" | "convertir">(props.actividadId ? "ver" : "editar");
const elemento = ref<ElementoChecklist | null>(null);
const cargando = ref(!!props.actividadId);
const ocupado = ref(false);
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");

const p = computed(() => props.pizarra);
const puede = computed(() => p.value.permisos);
const tiposDe = computed(() => p.value.tipos.filter((tp) => actividad.value?.tipos.includes(tp.id)));
const historial = computed(() => actividad.value?.historial ?? []);
const faltanPermisos = computed(() => !puede.value.mover || !puede.value.editar || !puede.value.eliminar);

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
}

async function cargar() {
  if (!props.actividadId) {
    llenarForm(null);
    return;
  }
  cargando.value = true;
  try {
    actividad.value = await api<Actividad>(`actividades/${props.actividadId}/`);
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudo abrir la actividad."));
    emit("cerrar");
  } finally {
    cargando.value = false;
  }
}
watch(() => props.actividadId, cargar, { immediate: true });

function editar() {
  llenarForm(actividad.value);
  modo.value = "editar";
}

/** Formulario de actividad nueva, prellenado con el elemento y enlazado a él (§4.6). */
function convertir(e: ElementoChecklist) {
  const t = actividad.value!;
  llenarForm(null);
  // Los elementos llegan a 400 caracteres y el título a 200: el resto va a la descripción.
  [form.titulo, form.descripcion] = partirTitulo(e.texto);
  form.lista = t.lista;
  form.asignados = t.asignados.map((u) => u.id);
  elemento.value = e;
  modo.value = "convertir";
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
    // Al editar, «Al completar» lo guarda la checklist al momento (no se pisa con el valor viejo).
    const datos = modo.value === "editar" && actividad.value ? todos : { ...todos, lista_al_completar };
    if (modo.value === "convertir" && elemento.value) {
      const r = await api<{ actividad: Actividad; nueva: Actividad }>(`checklist/${elemento.value.id}/convertir/`, "POST", {
        ...datos,
        checklist,
      });
      actividad.value = r.actividad;
      elemento.value = null;
      modo.value = "ver";
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
    modo.value = "ver";
    emit("guardada", actividad.value);
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

/** Cambiar de lista con un toque: queda al final (el orden se cambia arrastrando en el tablero). */
async function moverA(listaId: number) {
  const t = actividad.value;
  if (!t || t.lista === listaId || ocupado.value) return;
  ocupado.value = true;
  try {
    actividad.value = await api<Actividad>(`actividades/${t.id}/mover/`, "POST", { lista: listaId });
    emit("guardada", actividad.value);
    avisar(`Se movió a «${actividad.value.lista_nombre}».`);
  } catch (e) {
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

function cancelar() {
  if (actividad.value) {
    modo.value = "ver";
    elemento.value = null;
  } else emit("cerrar");
}

const esYo = (id: number | undefined) => id === sesion.usuario?.id;
const titulo = computed(() => {
  if (modo.value === "convertir") return "Nueva actividad";
  if (modo.value === "editar") return actividad.value ? "Editar actividad" : "Nueva actividad";
  return actividad.value?.titulo ?? "Actividad";
});
</script>

<template>
  <Hoja :titulo="titulo" @cerrar="emit('cerrar')">
    <div v-if="cargando" class="cargando" style="min-height: 120px">Cargando…</div>

    <!-- Detalle -->
    <template v-else-if="modo === 'ver' && actividad">
      <!-- Arriba y no al final: el historial crece y las dejaría cada vez más lejos (2026-10-06). -->
      <div v-if="puede.editar || puede.eliminar" class="acciones-detalle">
        <button v-if="puede.editar" class="btn btn-chico btn-secundario" @click="editar">
          <Icono nombre="lapiz" />Editar
        </button>
        <button v-if="puede.eliminar" class="btn btn-chico btn-peligro" @click="eliminar">
          <Icono nombre="basura" />Eliminar
        </button>
      </div>
      <div v-if="actividad.viene_de" class="viene-de">
        <Icono nombre="enlace" />
        <span
          >Viene de la checklist de
          <button @click="emit('abrir', actividad.viene_de.id)">{{ actividad.viene_de.titulo }}</button></span
        >
      </div>
      <div class="campo">
        <span class="etiqueta">Lista</span>
        <div v-if="puede.mover" class="elegir-lista" role="radiogroup" aria-label="Mover a la lista">
          <button
            v-for="l in p.listas"
            :key="l.id"
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
      <div class="campo">
        <span class="etiqueta">Historial · {{ historial.length }}</span>
        <ul class="historial">
          <li v-for="(h, i) in historial" :key="i">
            {{ h.usuario?.nombre ?? "Usuario eliminado" }}{{ esYo(h.usuario?.id) ? " (tú)" : "" }}
            <template v-if="h.nota">{{ h.nota }}</template>
            <template v-else-if="h.de">la movió de <Chips :lista="h.de" /> a <Chips :lista="h.a ?? ''" /></template>
            <template v-else>la creó en <Chips :lista="h.a ?? ''" /></template>
            <span class="cuando">{{ fechaHora(h.fecha) }}</span>
          </li>
        </ul>
      </div>
      <!-- Sin «Pizarra: …» ni «Creada por … el …» (Etapa 3.8): el historial ya dice quién y cuándo. -->
      <div v-if="p.archivada || (faltanPermisos && p.dueno)" class="meta">
        <span v-if="p.archivada">Pizarra archivada: solo lectura.</span>
        <span v-else-if="p.dueno"
          >Lo que no ves disponible depende de los permisos que te dio el dueño ({{ p.dueno.nombre }}).</span
        >
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
      <div class="campo">
        <label for="f-lista">Lista <span class="obligatorio" aria-hidden="true">*</span></label>
        <!-- Al editar, cambiarla es moverla al final de la nueva: requiere «Mover». -->
        <select
          id="f-lista"
          v-model="form.lista"
          aria-required="true"
          :disabled="modo === 'editar' && !!actividad && !puede.mover"
        >
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
      <!-- Editar: la checklist de la actividad, que se guarda al momento (sin convertir: dejaría el formulario). -->
      <Checklist
        v-if="modo === 'editar' && actividad"
        :actividad="actividad"
        :pizarra="p"
        sin-convertir
        @actualizada="checklistActualizada"
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
      <Adjuntos v-if="modo === 'editar' && actividad" :actividad="actividad" :pizarra="p" @actualizada="checklistActualizada" />
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
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="cancelar">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">{{ ocupado ? "Guardando…" : "Guardar" }}</button>
      </div>
    </form>
  </Hoja>
</template>
