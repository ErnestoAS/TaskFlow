<!--
  Confirmar el correo con el código de 6 dígitos (§7). Llega aquí quien acaba de registrarse o quien
  intenta entrar con una cuenta sin confirmar; en ambos casos el servidor ya mandó el código.
-->
<script setup lang="ts">
import { onUnmounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Logo from "../componentes/Logo.vue";
import { sesion } from "../sesion";
import type { Usuario } from "../tipos";
import { avisar } from "../ui";

const route = useRoute();
const router = useRouter();
const correo = typeof route.query.correo === "string" ? route.query.correo : "";
const codigo = ref("");
const error = ref("");
const ocupado = ref(false);

// El servidor pide un minuto entre envíos; el botón espera lo mismo para no dar un error seguro.
const espera = ref(60);
const reloj = setInterval(() => espera.value > 0 && espera.value--, 1000);
onUnmounted(() => clearInterval(reloj));

async function confirmar() {
  error.value = "";
  if (!/^\d{6}$/.test(codigo.value.trim())) {
    error.value = "Escribe los 6 dígitos del código.";
    return;
  }
  ocupado.value = true;
  try {
    sesion.usuario = await api<Usuario>("auth/verificar/", "POST", { correo, codigo: codigo.value.trim() });
    avisar("Se confirmó tu correo.");
    const siguiente = typeof route.query.siguiente === "string" ? route.query.siguiente : "/proyectos";
    await router.replace(siguiente);
  } catch (e) {
    error.value = e instanceof ErrorApi && e.campos.codigo ? e.campos.codigo : mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function reenviar() {
  error.value = "";
  try {
    await api("auth/verificar/reenviar/", "POST", { correo });
    espera.value = 60;
    avisar("Se envió un código nuevo.");
  } catch (e) {
    error.value = mensajeDeError(e);
  }
}
</script>

<template>
  <main class="acceso">
    <div class="marca"><Logo /><span>TaskFlow</span></div>
    <div class="caja">
      <h1>Confirma tu correo</h1>
      <template v-if="correo">
        <p class="intro">
          Te enviamos un código de 6 dígitos a <b>{{ correo }}</b>. Escríbelo para terminar. Si no lo ves, revisa la
          carpeta de spam.
        </p>
        <form novalidate @submit.prevent="confirmar">
          <div v-if="error" class="error-general" role="alert">{{ error }}</div>
          <div class="campo">
            <label for="codigo">Código</label>
            <input
              id="codigo"
              v-model="codigo"
              type="text"
              inputmode="numeric"
              autocomplete="one-time-code"
              maxlength="6"
              pattern="\d{6}"
            />
            <div class="ayuda">Vence en 15 minutos.</div>
          </div>
          <div class="fila-botones">
            <button type="button" class="btn btn-secundario" :disabled="espera > 0" @click="reenviar">
              {{ espera > 0 ? `Reenviar (${espera} s)` : "Reenviar código" }}
            </button>
            <button type="submit" class="btn btn-primario" :disabled="ocupado">
              {{ ocupado ? "Confirmando…" : "Confirmar" }}
            </button>
          </div>
        </form>
      </template>
      <template v-else>
        <p class="intro">Entra con tu correo y contraseña para recibir un código nuevo.</p>
        <RouterLink :to="{ name: 'entrar' }" class="btn btn-primario btn-bloque">Ir a Entrar</RouterLink>
      </template>
    </div>
    <p class="pie-acceso"><RouterLink :to="{ name: 'entrar' }">Volver a Entrar</RouterLink></p>
  </main>
</template>
