<!--
  Enlace del correo de invitación (§4.5). Solo la cuenta con el correo invitado puede aceptarla:
  - con sesión de esa cuenta: botón Aceptar;
  - con sesión de otra cuenta: se le pide salir y entrar con la correcta;
  - sin sesión y con cuenta existente: a Entrar, y de vuelta aquí;
  - sin sesión ni cuenta: crea la cuenta aquí con el correo invitado y entra directo a la pizarra.
-->
<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Logo from "../componentes/Logo.vue";
import { recargarPizarras } from "../pizarras";
import { salir, sesion } from "../sesion";
import type { Usuario } from "../tipos";
import { avisar } from "../ui";

interface InfoInvitacion {
  pizarra: string;
  correo: string;
  invitada_por: string | null;
  estado: "pendiente" | "aceptada" | "cancelada";
  existe_cuenta: boolean;
}

const props = defineProps<{ token: string }>();
const router = useRouter();

const info = ref<InfoInvitacion | null>(null);
const noExiste = ref(false);
const form = reactive({ nombre: "", primer_apellido: "", segundo_apellido: "", password: "" });
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");
const ocupado = ref(false);

const esMiCorreo = computed(
  () => !!sesion.usuario && sesion.usuario.correo.toLowerCase() === info.value?.correo.toLowerCase(),
);

onMounted(async () => {
  try {
    info.value = await api<InfoInvitacion>(`invitaciones/${props.token}/`);
  } catch {
    noExiste.value = true;
  }
});

async function irALaPizarra(id: number) {
  await recargarPizarras().catch(() => undefined);
  avisar(`Te uniste a «${info.value?.pizarra}».`);
  await router.replace({ name: "tablero", params: { id } });
}

async function aceptar() {
  errorGeneral.value = "";
  ocupado.value = true;
  try {
    const r = await api<{ pizarra: number }>(`invitaciones/${props.token}/aceptar/`, "POST");
    await irALaPizarra(r.pizarra);
  } catch (e) {
    errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function registrarse() {
  errores.value = {};
  errorGeneral.value = "";
  ocupado.value = true;
  try {
    const r = await api<{ pizarra: number; usuario: Usuario }>(`invitaciones/${props.token}/registro/`, "POST", form);
    sesion.usuario = r.usuario;
    await irALaPizarra(r.pizarra);
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function cambiarDeCuenta() {
  await salir();
  await router.replace({ name: "entrar", query: { siguiente: `/invitacion/${props.token}` } });
}
</script>

<template>
  <main class="acceso">
    <div class="marca"><Logo /><span>TaskFlow</span></div>
    <div class="caja">
      <template v-if="noExiste">
        <h1>Enlace no válido</h1>
        <p class="intro">Esta invitación no existe. Pide a quien te invitó que te la reenvíe.</p>
        <RouterLink :to="{ name: 'entrar' }" class="btn btn-secundario btn-bloque">Ir a TaskFlow</RouterLink>
      </template>

      <div v-else-if="!info" class="cargando" style="min-height: 120px">Cargando…</div>

      <template v-else>
        <h1>Invitación a «{{ info.pizarra }}»</h1>
        <p class="intro">
          <template v-if="info.invitada_por">{{ info.invitada_por }} te invitó</template
          ><template v-else>Te invitaron</template> a colaborar en esta pizarra de TaskFlow.
        </p>
        <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>

        <template v-if="info.estado !== 'pendiente'">
          <p class="intro">Esta invitación ya se usó o fue cancelada.</p>
          <RouterLink :to="{ name: 'pizarras' }" class="btn btn-secundario btn-bloque">Ir a TaskFlow</RouterLink>
        </template>

        <template v-else-if="sesion.usuario && esMiCorreo">
          <button class="btn btn-primario btn-bloque" :disabled="ocupado" @click="aceptar">Aceptar invitación</button>
        </template>

        <template v-else-if="sesion.usuario">
          <p class="intro">
            La invitación es para <b>{{ info.correo }}</b> y entraste como <b>{{ sesion.usuario.correo }}</b>. Sal y
            entra con la cuenta invitada para aceptarla.
          </p>
          <button class="btn btn-secundario btn-bloque" @click="cambiarDeCuenta">Salir y entrar con otra cuenta</button>
        </template>

        <template v-else-if="info.existe_cuenta">
          <p class="intro">Ya existe una cuenta con <b>{{ info.correo }}</b>. Entra con ella para aceptar.</p>
          <RouterLink
            :to="{ name: 'entrar', query: { siguiente: `/invitacion/${token}` } }"
            class="btn btn-primario btn-bloque"
            >Entrar para aceptar</RouterLink
          >
        </template>

        <form v-else novalidate @submit.prevent="registrarse">
          <div class="campo">
            <span class="etiqueta">Correo</span>
            <div class="correo-fijo">{{ info.correo }}</div>
          </div>
          <div class="campo">
            <label for="nombre">Nombre <span class="obligatorio" aria-hidden="true">*</span></label>
            <input id="nombre" aria-required="true" v-model="form.nombre" type="text" autocomplete="given-name" />
            <div v-if="errores.nombre" class="error">{{ errores.nombre }}</div>
          </div>
          <div class="campo">
            <label for="primer_apellido">Primer apellido <span class="obligatorio" aria-hidden="true">*</span></label>
            <input id="primer_apellido" aria-required="true" v-model="form.primer_apellido" type="text" autocomplete="family-name" />
            <div v-if="errores.primer_apellido" class="error">{{ errores.primer_apellido }}</div>
          </div>
          <div class="campo">
            <label for="segundo_apellido">Segundo apellido</label>
            <input id="segundo_apellido" v-model="form.segundo_apellido" type="text" autocomplete="off" />
          </div>
          <div class="campo">
            <label for="password">Contraseña <span class="obligatorio" aria-hidden="true">*</span></label>
            <input id="password" aria-required="true" v-model="form.password" type="password" autocomplete="new-password" />
            <div v-if="errores.password" class="error">{{ errores.password }}</div>
          </div>
          <button type="submit" class="btn btn-primario btn-bloque" :disabled="ocupado">
            {{ ocupado ? "Creando…" : "Crear cuenta y unirme" }}
          </button>
        </form>
      </template>
    </div>
  </main>
</template>
