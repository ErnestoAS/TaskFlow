<script setup lang="ts">
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { ErrorApi, mensajeDeError } from "../api";
import Logo from "../componentes/Logo.vue";
import { entrar, sesion } from "../sesion";

const route = useRoute();
const router = useRouter();
const correo = ref("");
const password = ref("");
const error = ref("");
const ocupado = ref(false);

async function enviar() {
  error.value = "";
  if (!correo.value.trim() || !password.value) {
    error.value = "Escribe tu correo y tu contraseña.";
    return;
  }
  ocupado.value = true;
  try {
    await entrar(correo.value.trim(), password.value);
    const siguiente = typeof route.query.siguiente === "string" ? route.query.siguiente : "/pizarras";
    await router.replace(siguiente);
  } catch (e) {
    // Cuenta sin confirmar: el servidor ya mandó (o reenvió) el código; se pasa a capturarlo.
    if (e instanceof ErrorApi && e.datos?.verificar) {
      await router.replace({ name: "verificar", query: { ...route.query, correo: String(e.datos.correo) } });
      return;
    }
    error.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <main class="acceso">
    <div class="marca"><Logo /><span>TaskFlow</span></div>
    <div class="caja">
      <h1>Entrar</h1>
      <p class="intro">Organiza tus actividades en pizarras con listas y tarjetas.</p>
      <form novalidate @submit.prevent="enviar">
        <div v-if="error" class="error-general" role="alert">{{ error }}</div>
        <div class="campo">
          <label for="correo">Correo</label>
          <input id="correo" v-model="correo" type="email" autocomplete="username" inputmode="email" />
        </div>
        <div class="campo">
          <label for="password">Contraseña</label>
          <input id="password" v-model="password" type="password" autocomplete="current-password" />
        </div>
        <button type="submit" class="btn btn-primario btn-bloque" :disabled="ocupado">
          {{ ocupado ? "Entrando…" : "Entrar" }}
        </button>
      </form>
    </div>
    <p class="pie-acceso">
      <RouterLink :to="{ name: 'recuperar', query: correo.trim() ? { correo: correo.trim() } : {} }"
        >¿Olvidaste tu contraseña?</RouterLink
      >
    </p>
    <p v-if="sesion.registroAbierto" class="pie-acceso">
      ¿No tienes cuenta? <RouterLink :to="{ name: 'registro' }">Crea una</RouterLink>
    </p>
    <p v-else class="pie-acceso">Para tener cuenta, pide a alguien que te invite a su pizarra.</p>
  </main>
</template>
