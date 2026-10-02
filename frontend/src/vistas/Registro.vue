<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Logo from "../componentes/Logo.vue";
import { sesion } from "../sesion";

const router = useRouter();
const form = reactive({ nombre: "", primer_apellido: "", segundo_apellido: "", correo: "", password: "" });
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");
const ocupado = ref(false);

async function enviar() {
  errores.value = {};
  errorGeneral.value = "";
  ocupado.value = true;
  try {
    // La cuenta queda sin sesión hasta confirmar el código que llega al correo.
    const r = await api<{ correo: string }>("auth/registro/", "POST", form);
    await router.replace({ name: "verificar", query: { correo: r.correo } });
  } catch (e) {
    if (e instanceof ErrorApi && Object.keys(e.campos).length) errores.value = e.campos;
    else errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}
</script>

<template>
  <main class="acceso">
    <div class="marca"><Logo /><span>TaskFlow</span></div>
    <div class="caja">
      <h1>Crear cuenta</h1>
      <p class="intro">Con tu cuenta puedes crear proyectos e invitar a otras personas.</p>
      <div v-if="!sesion.registroAbierto" class="error-general">El registro está cerrado. Pide una invitación.</div>
      <form v-else novalidate @submit.prevent="enviar">
        <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
        <div class="campo">
          <label for="nombre">Nombre</label>
          <input id="nombre" v-model="form.nombre" type="text" autocomplete="given-name" />
          <div v-if="errores.nombre" class="error">{{ errores.nombre }}</div>
        </div>
        <div class="campo">
          <label for="primer_apellido">Primer apellido</label>
          <input id="primer_apellido" v-model="form.primer_apellido" type="text" autocomplete="family-name" />
          <div v-if="errores.primer_apellido" class="error">{{ errores.primer_apellido }}</div>
        </div>
        <div class="campo">
          <label for="segundo_apellido">Segundo apellido <span style="text-transform: none; font-weight: 400">(opcional)</span></label>
          <input id="segundo_apellido" v-model="form.segundo_apellido" type="text" autocomplete="off" />
        </div>
        <div class="campo">
          <label for="correo">Correo</label>
          <input id="correo" v-model="form.correo" type="email" autocomplete="email" inputmode="email" />
          <div v-if="errores.correo" class="error">{{ errores.correo }}</div>
        </div>
        <div class="campo">
          <label for="password">Contraseña</label>
          <input id="password" v-model="form.password" type="password" autocomplete="new-password" />
          <div v-if="errores.password" class="error">{{ errores.password }}</div>
          <div v-else class="ayuda">Al menos 8 caracteres, que no sea solo números ni muy común. Te enviaremos un código a tu correo para confirmarlo.</div>
        </div>
        <button type="submit" class="btn btn-primario btn-bloque" :disabled="ocupado">
          {{ ocupado ? "Creando…" : "Crear cuenta" }}
        </button>
      </form>
    </div>
    <p class="pie-acceso">¿Ya tienes cuenta? <RouterLink :to="{ name: 'entrar' }">Entra</RouterLink></p>
  </main>
</template>
