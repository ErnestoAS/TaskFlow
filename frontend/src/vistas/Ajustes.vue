<!--
  Miembros y ajustes del proyecto (§4.5): invitar, reenviar o cancelar invitaciones, permisos por
  miembro, transferir, quitar, tipos de tarjeta, archivar/restaurar, eliminar y salir.
  Solo el dueño ve los controles de miembros; los tipos, quien tenga «Gestionar tipos».
-->
<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Avatar from "../componentes/Avatar.vue";
import Cabecera from "../componentes/Cabecera.vue";
import FormProyecto from "../componentes/FormProyecto.vue";
import FormTipo from "../componentes/FormTipo.vue";
import Icono from "../componentes/Icono.vue";
import { recargarProyectos } from "../proyectos";
import { sesion } from "../sesion";
import type { Miembro, Permiso, ProyectoDetalle, Tipo } from "../tipos";
import { avisar, confirmar } from "../ui";
import { fechaHora, MUESTRAS, PERMISOS, plural } from "../utilidades";

const props = defineProps<{ id: number }>();
const router = useRouter();

const p = ref<ProyectoDetalle | null>(null);
const correo = ref("");
const errorInvitar = ref("");
const ocupado = ref(false);
const formTipo = ref<{ tipo: Tipo | null } | null>(null);
const renombrar = ref(false);

const soyDueno = computed(() => p.value?.rol === "dueno");
const activo = computed(() => !!p.value && !p.value.archivado);
const gestionaTipos = computed(() => !!p.value?.permisos.gestionar_tipos);
const totalTarjetas = computed(() =>
  p.value ? p.value.conteos.pendiente + p.value.conteos.en_curso + p.value.conteos.finalizada : 0,
);

async function cargar() {
  try {
    p.value = await api<ProyectoDetalle>(`proyectos/${props.id}/`);
  } catch (e) {
    avisar(e instanceof ErrorApi && e.estado === 404 ? "Ese proyecto no existe o ya no eres miembro." : mensajeDeError(e));
    await router.replace({ name: "proyectos" });
  }
}
watch(() => props.id, cargar, { immediate: true });

/** Ejecuta una acción que devuelve el proyecto actualizado. */
async function hacer(ruta: string, metodo: "POST" | "PATCH" | "DELETE", datos: unknown, aviso: string) {
  ocupado.value = true;
  try {
    p.value = await api<ProyectoDetalle>(ruta, metodo, datos);
    avisar(aviso);
    return true;
  } catch (e) {
    avisar(mensajeDeError(e));
    return false;
  } finally {
    ocupado.value = false;
  }
}

async function invitar() {
  errorInvitar.value = "";
  const c = correo.value.trim();
  if (!c || !c.includes("@")) {
    errorInvitar.value = "Escribe un correo válido.";
    return;
  }
  ocupado.value = true;
  try {
    p.value = await api<ProyectoDetalle>(`proyectos/${props.id}/invitaciones/`, "POST", { correo: c });
    correo.value = "";
    avisar(`Se envió la invitación a ${c}.`);
  } catch (e) {
    errorInvitar.value = e instanceof ErrorApi ? (e.campos.correo ?? e.message) : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

const reenviar = (invId: number, c: string) =>
  hacer(`proyectos/${props.id}/invitaciones/${invId}/reenviar/`, "POST", undefined, `Se reenvió la invitación a ${c}.`);

async function cancelarInvitacion(invId: number, c: string) {
  if (!(await confirmar(`¿Cancelar la invitación a ${c}? El enlace que recibió dejará de funcionar.`, "Cancelar invitación")))
    return;
  await hacer(`proyectos/${props.id}/invitaciones/${invId}/cancelar/`, "POST", undefined, "Se canceló la invitación.");
}

const alternarPermiso = (m: Miembro, k: Permiso) =>
  hacer(`proyectos/${props.id}/miembros/${m.usuario.id}/`, "PATCH", { [k]: !m.permisos[k] }, "Se actualizaron los permisos.");

async function transferir(m: Miembro) {
  const ok = await confirmar(
    `¿Transferir «${p.value?.nombre}» a ${m.usuario.nombre}? Será el nuevo dueño y tú quedarás como miembro con todos los permisos sobre las tarjetas. Solo esa persona podrá devolvértelo.`,
    "Transferir",
  );
  if (ok && (await hacer(`proyectos/${props.id}/transferir/`, "POST", { usuario: m.usuario.id }, `Ahora ${m.usuario.nombre} es el dueño.`)))
    recargarProyectos().catch(() => undefined);
}

async function quitar(m: Miembro) {
  const ok = await confirmar(
    `¿Quitar a ${m.usuario.nombre} del proyecto? Dejará de ver sus tarjetas y se le quitará de las que tenga asignadas.`,
    "Quitar",
  );
  if (ok) await hacer(`proyectos/${props.id}/miembros/${m.usuario.id}/`, "DELETE", undefined, `Se quitó a ${m.usuario.nombre}.`);
}

async function eliminarTipo(tp: Tipo) {
  const n = tp.n_tarjetas ?? 0;
  const ok = await confirmar(
    `¿Eliminar el tipo «${tp.nombre}»? Se quitará de ${plural(n, "tarjeta")}; las tarjetas no se borran.`,
    "Eliminar tipo",
  );
  if (!ok) return;
  try {
    await api(`proyectos/${props.id}/tipos/${tp.id}/`, "DELETE");
    avisar("Se eliminó el tipo.");
    await cargar();
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

async function tipoGuardado() {
  formTipo.value = null;
  await cargar();
}

async function archivar() {
  const ok = await confirmar(
    `¿Archivar «${p.value?.nombre}»? Queda en solo lectura para todos sus miembros: nadie podrá crear, editar ni mover tarjetas. Puedes restaurarlo cuando quieras.`,
    "Archivar",
  );
  if (ok && (await hacer(`proyectos/${props.id}/archivar/`, "POST", undefined, "Se archivó el proyecto.")))
    recargarProyectos().catch(() => undefined);
}

async function restaurar() {
  if (await hacer(`proyectos/${props.id}/restaurar/`, "POST", undefined, "Se restauró el proyecto."))
    recargarProyectos().catch(() => undefined);
}

async function salirOEliminar(accion: "eliminar" | "salir") {
  const nombre = p.value?.nombre;
  const ok = await confirmar(
    accion === "eliminar"
      ? `¿Eliminar «${nombre}» y sus ${plural(totalTarjetas.value, "tarjeta")}? Se borra para todos sus miembros y no se puede deshacer.`
      : `¿Salir de «${nombre}»? Dejarás de ver sus tarjetas y se te quitará de las que tengas asignadas.`,
    accion === "eliminar" ? "Eliminar proyecto" : "Salir",
  );
  if (!ok) return;
  try {
    if (accion === "eliminar") await api(`proyectos/${props.id}/`, "DELETE");
    else await api(`proyectos/${props.id}/salir/`, "POST");
    avisar(accion === "eliminar" ? `Se eliminó «${nombre}».` : `Saliste de «${nombre}».`);
    await recargarProyectos().catch(() => undefined);
    await router.replace({ name: "proyectos" });
  } catch (e) {
    avisar(mensajeDeError(e));
  }
}

async function renombrado(np: ProyectoDetalle) {
  renombrar.value = false;
  p.value = np;
  recargarProyectos().catch(() => undefined);
}
</script>

<template>
  <Cabecera :titulo="p?.nombre ?? 'Proyecto'" sub="Miembros y ajustes" :atras="{ name: 'tablero', params: { id } }" />
  <main class="contenido" style="max-width: 760px">
    <div v-if="!p" class="cargando">Cargando…</div>
    <template v-else>
      <div v-if="soyDueno && activo" class="invitar">
        <form class="campo" style="margin: 0" novalidate @submit.prevent="invitar">
          <label for="correo-inv">Invitar por correo</label>
          <div class="linea">
            <input id="correo-inv" v-model="correo" type="email" inputmode="email" placeholder="nombre@ejemplo.mx" />
            <button type="submit" class="btn btn-primario" :disabled="ocupado">Invitar</button>
          </div>
          <div v-if="errorInvitar" class="error">{{ errorInvitar }}</div>
          <div class="ayuda">
            Le llega un correo con un enlace que no vence. Si aún no tiene cuenta, la crea desde ahí y entra directo al
            proyecto con permiso de crear, editar y cambiar estatus (puedes cambiarlo abajo).
          </div>
        </form>
      </div>
      <div v-else-if="!soyDueno" class="aviso">
        <Icono nombre="info" />
        <span
          >Solo el dueño del proyecto ({{ p.dueno?.nombre }}) puede invitar, quitar personas y decidir qué puede hacer cada
          miembro con las tarjetas.</span
        >
      </div>

      <div class="seccion-titulo">Miembros · {{ p.miembros.length }}</div>
      <div class="tarjeta-blanca">
        <div v-for="m in p.miembros" :key="m.usuario.id" class="persona">
          <Avatar :usuario="m.usuario" />
          <div class="nombre">
            {{ m.usuario.nombre }}{{ m.usuario.id === sesion.usuario?.id ? " (tú)" : "" }}<small>{{ m.usuario.correo }}</small>
          </div>
          <span v-if="m.rol === 'dueno'" class="etiqueta-rol">Dueña/o</span>
          <div v-else-if="soyDueno" class="acciones-persona">
            <button class="btn btn-chico btn-secundario" :disabled="ocupado" @click="transferir(m)">Hacer dueño</button>
            <button v-if="activo" class="btn btn-chico btn-peligro" :disabled="ocupado" @click="quitar(m)">Quitar</button>
          </div>
          <template v-if="m.rol !== 'dueno'">
            <div v-if="soyDueno && activo" class="permisos" role="group" :aria-label="`Permisos de ${m.usuario.nombre}`">
              <button
                v-for="[k, txt] in PERMISOS"
                :key="k"
                :aria-pressed="m.permisos[k]"
                :disabled="ocupado"
                @click="alternarPermiso(m, k)"
              >
                <Icono nombre="palomita" />{{ txt }}
              </button>
            </div>
            <div v-else class="permisos">
              <span class="rotulo">Puede:</span>
              <template v-if="PERMISOS.some(([k]) => m.permisos[k])">
                <span v-for="[k, txt] in PERMISOS.filter(([k]) => m.permisos[k])" :key="k" class="si"
                  ><Icono nombre="palomita" />{{ txt }}</span
                >
              </template>
              <span v-else>Solo ver tarjetas</span>
            </div>
          </template>
        </div>
      </div>

      <template v-if="p.invitaciones.length">
        <div class="seccion-titulo">Invitaciones pendientes · {{ p.invitaciones.length }}</div>
        <div class="tarjeta-blanca">
          <div v-for="inv in p.invitaciones" :key="inv.id" class="persona">
            <span class="avatar grande mas"><Icono nombre="correo" /></span>
            <div class="nombre">
              {{ inv.correo }}<small
                >Enviada {{ fechaHora(inv.enviada_en) }}{{ inv.veces_enviada > 1 ? ` · ${inv.veces_enviada} envíos` : "" }} · no
                vence</small
              >
            </div>
            <div v-if="activo" class="acciones-persona">
              <button class="btn btn-chico btn-secundario" :disabled="ocupado" @click="reenviar(inv.id, inv.correo)">Reenviar</button>
              <button class="btn btn-chico btn-peligro" :disabled="ocupado" @click="cancelarInvitacion(inv.id, inv.correo)">
                Cancelar
              </button>
            </div>
          </div>
        </div>
      </template>

      <div class="seccion-titulo">Tipos de tarjeta · {{ p.tipos.length }}</div>
      <div class="tarjeta-blanca">
        <div v-for="tp in p.tipos" :key="tp.id" class="fila-tipo">
          <span class="muestra-color" :style="{ '--tipo': tp.color }" />
          <div class="nombre">
            {{ tp.nombre }}<small>{{ tp.descripcion ? `${tp.descripcion} · ` : "" }}{{ plural(tp.n_tarjetas ?? 0, "tarjeta") }}</small>
          </div>
          <div v-if="gestionaTipos" class="acciones-persona">
            <button class="btn btn-chico btn-secundario" @click="formTipo = { tipo: tp }">Editar</button>
            <button class="btn btn-chico btn-peligro" @click="eliminarTipo(tp)">Eliminar</button>
          </div>
        </div>
        <div v-if="!p.tipos.length" class="vacio" style="padding: 16px">Este proyecto aún no tiene tipos.</div>
        <div v-if="gestionaTipos" style="padding: 10px 0 8px">
          <button class="btn btn-secundario btn-bloque" @click="formTipo = { tipo: null }">
            <Icono nombre="masChico" /> Nuevo tipo
          </button>
        </div>
      </div>
      <div v-if="!gestionaTipos && activo" class="ayuda" style="font-size: 12px; color: var(--tf-text-muted); margin: 6px 4px 0">
        Crear y editar tipos lo puede el dueño o quien tenga el permiso «Gestionar tipos».
      </div>

      <div class="seccion-titulo">Proyecto</div>
      <div v-if="soyDueno" class="tarjeta-blanca" style="padding: 14px; display: flex; flex-direction: column; gap: 10px">
        <button v-if="activo" class="btn btn-secundario btn-bloque" @click="renombrar = true">Cambiar nombre</button>
        <button v-if="p.archivado" class="btn btn-secundario btn-bloque" :disabled="ocupado" @click="restaurar">
          Restaurar proyecto
        </button>
        <button v-else class="btn btn-secundario btn-bloque" :disabled="ocupado" @click="archivar">
          <Icono nombre="archivo" /> Archivar proyecto
        </button>
        <button class="btn btn-peligro btn-bloque" @click="salirOEliminar('eliminar')">Eliminar proyecto</button>
        <div class="ayuda" style="font-size: 12px; color: var(--tf-text-muted)">
          Para salir del proyecto, primero transfiérelo a otro miembro con «Hacer dueño».
        </div>
      </div>
      <button v-else class="btn btn-peligro btn-bloque" @click="salirOEliminar('salir')">Salir del proyecto</button>
    </template>
  </main>

  <FormTipo
    v-if="formTipo && p"
    :proyecto-id="p.id"
    :tipo="formTipo.tipo"
    :sugerido="MUESTRAS[p.tipos.length % MUESTRAS.length]"
    @cerrar="formTipo = null"
    @guardado="tipoGuardado"
  />
  <FormProyecto v-if="renombrar && p" :proyecto="p" @cerrar="renombrar = false" @guardado="renombrado" />
</template>
