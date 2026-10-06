<!--
  Detalle de una tarjeta y su formulario, en la misma hoja (§5). Modos:
  - ver: lista (cambiarla con un toque), prioridad, tipos, descripción, fechas, checklist,
    asignados e historial; «Viene de» si nació de la checklist de otra tarjeta;
  - editar: alta (con `tarjetaId` null, en `listaInicial`) o edición;
  - convertir: alta de una tarjeta enlazada a un elemento de la checklist (§4.6), con
    «Marcar como terminado cuando pase a».
  Lo que el usuario no puede hacer no se muestra o queda deshabilitado según los permisos que le
  dio el dueño (pizarra.permisos; todo en falso si la pizarra está archivada).
-->
<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";

import { api, ErrorApi, mensajeDeError } from "../api";
import { sesion } from "../sesion";
import type { ElementoChecklist, PizarraDetalle, Prioridad, Tarjeta } from "../tipos";
import { avisar, confirmar } from "../ui";
import { fechaHora, fechaLarga, hoyIso, PRIORIDADES } from "../utilidades";
import Avatar from "./Avatar.vue";
import Checklist from "./Checklist.vue";
import Chips from "./Chips.vue";
import Hoja from "./Hoja.vue";
import Icono from "./Icono.vue";

const props = defineProps<{ pizarra: PizarraDetalle; tarjetaId: number | null; listaInicial?: number }>();
const emit = defineEmits<{
  cerrar: [];
  guardada: [t: Tarjeta];
  eliminada: [id: number];
  /** Abrir otra tarjeta (la de origen o una creada desde la checklist). */
  abrir: [id: number];
}>();

const tarjeta = ref<Tarjeta | null>(null);
const modo = ref<"ver" | "editar" | "convertir">(props.tarjetaId ? "ver" : "editar");
const elemento = ref<ElementoChecklist | null>(null);
const cargando = ref(!!props.tarjetaId);
const ocupado = ref(false);
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");

const p = computed(() => props.pizarra);
const puede = computed(() => p.value.permisos);
const tiposDe = computed(() => p.value.tipos.filter((tp) => tarjeta.value?.tipos.includes(tp.id)));
const historial = computed(() => tarjeta.value?.historial ?? []);
const faltanPermisos = computed(() => !puede.value.mover || !puede.value.editar || !puede.value.eliminar);
/** Al convertir, la lista que marca el elemento como hecho: la de cierre o, si no hay, la última. */
const listaTerminadoSugerida = computed(
  () => (p.value.listas.find((l) => l.es_cierre) ?? p.value.listas[p.value.listas.length - 1])?.id ?? "",
);

const form = reactive({
  titulo: "",
  descripcion: "",
  lista: 0,
  prioridad: "media" as Prioridad,
  fecha_inicio: "",
  fecha_fin: "",
  tipos: [] as number[],
  asignados: [] as number[],
  lista_terminado: "" as number | "",
});

function llenarForm(t: Tarjeta | null) {
  form.titulo = t?.titulo ?? "";
  form.descripcion = t?.descripcion ?? "";
  form.lista = t?.lista ?? props.listaInicial ?? p.value.listas[0]?.id ?? 0;
  form.prioridad = t?.prioridad ?? "media";
  form.fecha_inicio = t?.fecha_inicio ?? hoyIso();
  form.fecha_fin = t?.fecha_fin ?? "";
  form.tipos = [...(t?.tipos ?? [])];
  form.asignados = (t?.asignados ?? []).map((u) => u.id);
  errores.value = {};
  errorGeneral.value = "";
}

async function cargar() {
  if (!props.tarjetaId) {
    llenarForm(null);
    return;
  }
  cargando.value = true;
  try {
    tarjeta.value = await api<Tarjeta>(`tarjetas/${props.tarjetaId}/`);
  } catch (e) {
    avisar(mensajeDeError(e, "No se pudo abrir la tarjeta."));
    emit("cerrar");
  } finally {
    cargando.value = false;
  }
}
watch(() => props.tarjetaId, cargar, { immediate: true });

function editar() {
  llenarForm(tarjeta.value);
  modo.value = "editar";
}

/** Formulario de tarjeta nueva, prellenado con el elemento y enlazado a él (§4.6). */
function convertir(e: ElementoChecklist) {
  const t = tarjeta.value!;
  llenarForm(null);
  form.titulo = e.texto;
  form.lista = t.lista;
  form.asignados = t.asignados.map((u) => u.id);
  form.lista_terminado = listaTerminadoSugerida.value;
  elemento.value = e;
  modo.value = "convertir";
}

function datosForm() {
  const { lista_terminado, ...datos } = form;
  return { ...datos, titulo: form.titulo.trim(), fecha_fin: form.fecha_fin || null, lista_terminado };
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
    const { lista_terminado, lista, ...datos } = datosForm();
    if (modo.value === "convertir" && elemento.value) {
      const r = await api<{ tarjeta: Tarjeta; nueva: Tarjeta }>(`checklist/${elemento.value.id}/convertir/`, "POST", {
        ...datos,
        lista,
        lista_terminado: lista_terminado || null,
      });
      tarjeta.value = r.tarjeta;
      elemento.value = null;
      modo.value = "ver";
      avisar("Se creó la tarjeta desde la checklist.");
      emit("guardada", r.nueva);
      return;
    }
    const t = tarjeta.value
      ? await api<Tarjeta>(`tarjetas/${tarjeta.value.id}/`, "PATCH", datos)
      : await api<Tarjeta>(`pizarras/${p.value.id}/tarjetas/`, "POST", { ...datos, lista });
    avisar(tarjeta.value ? "Se guardaron los cambios." : "Se creó la tarjeta.");
    tarjeta.value = t;
    modo.value = "ver";
    emit("guardada", t);
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

/** Cambiar de lista con un toque: queda al final (el orden se cambia arrastrando en el tablero). */
async function moverA(listaId: number) {
  const t = tarjeta.value;
  if (!t || t.lista === listaId || ocupado.value) return;
  ocupado.value = true;
  try {
    tarjeta.value = await api<Tarjeta>(`tarjetas/${t.id}/mover/`, "POST", { lista: listaId });
    emit("guardada", tarjeta.value);
    avisar(`Se movió a «${tarjeta.value.lista_nombre}».`);
  } catch (e) {
    avisar(mensajeDeError(e));
  } finally {
    ocupado.value = false;
  }
}

function checklistActualizada(t: Tarjeta) {
  tarjeta.value = t;
  emit("guardada", t);
}

async function eliminar() {
  const t = tarjeta.value;
  if (!t) return;
  const ok = await confirmar(`¿Eliminar la tarjeta «${t.titulo}»? Esta acción no se puede deshacer.`, "Eliminar");
  if (!ok) return;
  try {
    await api(`tarjetas/${t.id}/`, "DELETE");
    avisar("Se eliminó la tarjeta.");
    emit("eliminada", t.id);
    emit("cerrar");
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

function cancelar() {
  if (tarjeta.value) {
    modo.value = "ver";
    elemento.value = null;
  } else emit("cerrar");
}

const esYo = (id: number | undefined) => id === sesion.usuario?.id;
const titulo = computed(() => {
  if (modo.value === "convertir") return "Nueva tarjeta";
  if (modo.value === "editar") return tarjeta.value ? "Editar tarjeta" : "Nueva tarjeta";
  return tarjeta.value?.titulo ?? "Tarjeta";
});
</script>

<template>
  <Hoja :titulo="titulo" @cerrar="emit('cerrar')">
    <div v-if="cargando" class="cargando" style="min-height: 120px">Cargando…</div>

    <!-- Detalle -->
    <template v-else-if="modo === 'ver' && tarjeta">
      <div v-if="tarjeta.viene_de" class="viene-de">
        <Icono nombre="enlace" />
        <span
          >Viene de la checklist de
          <button @click="emit('abrir', tarjeta.viene_de.id)">{{ tarjeta.viene_de.titulo }}</button></span
        >
      </div>
      <div class="campo">
        <span class="etiqueta">Lista</span>
        <template v-if="puede.mover">
          <div class="elegir-lista" role="radiogroup" aria-label="Mover a la lista">
            <button
              v-for="l in p.listas"
              :key="l.id"
              role="radio"
              :aria-checked="tarjeta.lista === l.id"
              :disabled="ocupado"
              @click="moverA(l.id)"
            >
              <Icono v-if="tarjeta.lista === l.id" nombre="palomita" />{{ l.nombre }}
            </button>
          </div>
          <div class="ayuda">
            Toca una lista para moverla (queda al final). Para cambiar su orden, arrástrala en el tablero (en el teléfono,
            mantenla presionada).
          </div>
        </template>
        <Chips v-else :lista="tarjeta.lista_nombre" />
      </div>
      <div class="campo"><span class="etiqueta">Prioridad</span><Chips :prioridad="tarjeta.prioridad" /></div>
      <div class="campo">
        <span class="etiqueta">Tipos</span>
        <div v-if="tiposDe.length" class="tipos-tarjeta"><Chips v-for="tp in tiposDe" :key="tp.id" :tipo="tp" /></div>
        <span v-else class="ayuda" style="font-size: 14px">Sin tipo</span>
      </div>
      <div class="campo">
        <span class="etiqueta">Descripción</span>
        <p v-if="tarjeta.descripcion" class="texto-largo">{{ tarjeta.descripcion }}</p>
        <span v-else class="ayuda" style="font-size: 14px">Sin descripción</span>
      </div>
      <div class="dos-campos">
        <div class="campo">
          <span class="etiqueta">Fecha de inicio</span>
          <span class="chip fecha"><Icono nombre="calendario" />{{ fechaLarga(tarjeta.fecha_inicio) }}</span>
        </div>
        <div class="campo">
          <span class="etiqueta">Fecha límite</span>
          <Chips v-if="tarjeta.fecha_fin" :fecha="tarjeta" />
          <span v-else class="ayuda" style="font-size: 14px">Sin fecha</span>
        </div>
      </div>
      <Checklist
        :tarjeta="tarjeta"
        :pizarra="p"
        @actualizada="checklistActualizada"
        @convertir="convertir"
        @abrir="(id) => emit('abrir', id)"
      />
      <div class="campo">
        <span class="etiqueta">Asignada a · {{ tarjeta.asignados.length }}</span>
        <div class="personas">
          <div v-for="u in tarjeta.asignados" :key="u.id" class="persona">
            <Avatar :usuario="u" />
            <div class="nombre">{{ u.nombre }}{{ esYo(u.id) ? " (tú)" : "" }}</div>
          </div>
          <span v-if="!tarjeta.asignados.length" class="ayuda" style="font-size: 14px">Sin asignar</span>
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
        <div class="ayuda">Ordenarla dentro de la misma lista no se registra.</div>
      </div>
      <div v-if="puede.editar || puede.eliminar" class="fila-botones">
        <button v-if="puede.editar" class="btn btn-secundario" @click="editar">Editar</button>
        <button v-if="puede.eliminar" class="btn btn-chico btn-peligro" @click="eliminar">Eliminar</button>
      </div>
      <div class="meta">
        <span>Pizarra: {{ p.nombre }}</span>
        <span>Creada{{ tarjeta.creada_por ? ` por ${tarjeta.creada_por.nombre}` : "" }} el {{ fechaHora(tarjeta.creado_en) }}</span>
        <span v-if="p.archivada">Pizarra archivada: solo lectura.</span>
        <span v-else-if="faltanPermisos && p.dueno"
          >Lo que no ves disponible depende de los permisos que te dio el dueño ({{ p.dueno.nombre }}).</span
        >
      </div>
    </template>

    <!-- Alta / edición / conversión -->
    <form v-else novalidate @submit.prevent="guardar">
      <div v-if="modo === 'convertir' && tarjeta" class="viene-de">
        <Icono nombre="enlace" />
        <span>Desde la checklist de <b>{{ tarjeta.titulo }}</b>. Quedarán enlazadas.</span>
      </div>
      <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
      <div class="campo">
        <label for="f-titulo">Título</label>
        <input id="f-titulo" v-model="form.titulo" type="text" maxlength="200" placeholder="¿Qué hay que hacer?" />
        <div v-if="errores.titulo" class="error">{{ errores.titulo }}</div>
      </div>
      <div v-if="!tarjeta || modo === 'convertir'" class="campo">
        <label for="f-lista">Lista</label>
        <select id="f-lista" v-model="form.lista">
          <option v-for="l in p.listas" :key="l.id" :value="l.id">{{ l.nombre }}</option>
        </select>
        <div class="ayuda">Se agrega al final de la lista.</div>
        <div v-if="errores.lista" class="error">{{ errores.lista }}</div>
      </div>
      <div v-if="modo === 'convertir'" class="campo">
        <label for="f-termina">Marcar como terminado cuando pase a</label>
        <select id="f-termina" v-model="form.lista_terminado">
          <option v-for="l in p.listas" :key="l.id" :value="l.id">{{ l.nombre }}</option>
          <option value="">Ninguna: lo palomeo a mano</option>
        </select>
        <div class="ayuda">
          Cuando esta tarjeta llegue a esa lista, «{{ elemento?.texto }}» se palomea solo en la checklist de «{{
            tarjeta?.titulo
          }}».
        </div>
        <div v-if="errores.lista_terminado" class="error">{{ errores.lista_terminado }}</div>
      </div>
      <div class="campo">
        <label for="f-desc">Descripción <span class="opcional">(opcional)</span></label>
        <textarea id="f-desc" v-model="form.descripcion" placeholder="Detalles, criterios de terminado…" />
      </div>
      <div class="campo">
        <span class="etiqueta">Prioridad</span>
        <div class="elegir-prioridad" role="radiogroup" aria-label="Prioridad">
          <label v-for="[k, txt] in PRIORIDADES" :key="k">
            <input v-model="form.prioridad" type="radio" name="prioridad" :value="k" />
            <span class="chip" :class="`prio-${k}`"><span class="punto" />{{ txt }}</span>
          </label>
        </div>
      </div>
      <div class="dos-campos">
        <div class="campo">
          <label for="f-inicio">Fecha de inicio</label>
          <input id="f-inicio" v-model="form.fecha_inicio" type="date" />
          <div v-if="errores.fecha_inicio" class="error">{{ errores.fecha_inicio }}</div>
        </div>
        <div class="campo">
          <label for="f-fecha">Fecha límite <span class="opcional">(opcional)</span></label>
          <input id="f-fecha" v-model="form.fecha_fin" type="date" />
          <div v-if="errores.fecha_fin" class="error">{{ errores.fecha_fin }}</div>
        </div>
      </div>
      <div class="ayuda" style="margin: -8px 0 16px">
        La fecha de inicio es hoy por omisión; cámbiala si la actividad empezó o te la pidieron antes de capturarla.
        <template v-if="tarjeta && modo === 'editar'"> La tarjeta se capturó el {{ fechaHora(tarjeta.creado_en) }}.</template>
      </div>
      <div class="campo">
        <span class="etiqueta">Tipos <span class="opcional">(opcional, uno o más)</span></span>
        <div v-if="p.tipos.length" class="elegir-tipos">
          <label v-for="tp in p.tipos" :key="tp.id">
            <input v-model="form.tipos" type="checkbox" :value="tp.id" />
            <span class="chip tipo" :style="{ '--tipo': tp.color }"><span class="punto" />{{ tp.nombre }}</span>
          </label>
        </div>
        <div v-else class="ayuda">Esta pizarra aún no tiene tipos.</div>
        <div v-if="errores.tipos" class="error">{{ errores.tipos }}</div>
      </div>
      <div class="campo">
        <span class="etiqueta">Asignar a <span class="opcional">(opcional)</span></span>
        <div class="personas">
          <label v-for="m in p.miembros" :key="m.usuario.id" class="persona">
            <input v-model="form.asignados" type="checkbox" :value="m.usuario.id" />
            <Avatar :usuario="m.usuario" />
            <span class="nombre">{{ m.usuario.nombre }}{{ esYo(m.usuario.id) ? " (tú)" : "" }}</span>
          </label>
        </div>
        <div class="ayuda">Solo aparecen los miembros de «{{ p.nombre }}». Puede quedar sin asignar.</div>
        <div v-if="errores.asignados" class="error">{{ errores.asignados }}</div>
      </div>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="cancelar">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">{{ ocupado ? "Guardando…" : "Guardar" }}</button>
      </div>
    </form>
  </Hoja>
</template>
