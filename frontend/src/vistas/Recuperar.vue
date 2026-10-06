<!--
  «¿Olvidaste tu contraseña?» (§7): 1) el correo, 2) el código que llega ahí y la contraseña nueva.
  El servidor responde igual exista o no la cuenta, así que el paso 2 se muestra siempre.
-->
<script setup lang="ts">
import { onUnmounted, reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { api, ErrorApi, mensajeDeError } from "../api";
import Logo from "../componentes/Logo.vue";
import { sesion } from "../sesion";
import type { Usuario } from "../tipos";
import { avisar } from "../ui";

const route = useRoute();
const router = useRouter();
const paso = ref<1 | 2>(1);
const form = reactive({
  correo: typeof route.query.correo === "string" ? route.query.correo : "",
  codigo: "",
  password: "",
});
const errores = ref<Record<string, string>>({});
const errorGeneral = ref("");
const ocupado = ref(false);

const espera = ref(0);
const reloj = setInterval(() => espera.value > 0 && espera.value--, 1000);
onUnmounted(() => clearInterval(reloj));

async function pedirCodigo() {
  errores.value = {};
  errorGeneral.value = "";
  if (!form.correo.trim()) {
    errores.value = { correo: "Escribe tu correo." };
    return;
  }
  ocupado.value = true;
  try {
    await api("auth/recuperar/", "POST", { correo: form.correo.trim() });
    paso.value = 2;
    espera.value = 60;
  } catch (e) {
    errorGeneral.value = mensajeDeError(e);
  } finally {
    ocupado.value = false;
  }
}

async function cambiar() {
  errores.value = {};
  errorGeneral.value = "";
  ocupado.value = true;
  try {
    sesion.usuario = await api<Usuario>("auth/recuperar/confirmar/", "POST", {
      correo: form.correo.trim(),
      codigo: form.codigo.trim(),
      password: form.password,
    });
    avisar("Se cambió tu contraseña.");
    await router.replace({ name: "pizarras" });
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
      <h1>Recuperar contraseña</h1>
      <form v-if="paso === 1" novalidate @submit.prevent="pedirCodigo">
        <p class="intro">Escribe el correo de tu cuenta y te enviaremos un código para poner una contraseña nueva.</p>
        <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
        <div class="campo">
          <label for="correo">Correo</label>
          <input id="correo" v-model="form.correo" type="email" autocomplete="username" inputmode="email" />
          <div v-if="errores.correo" class="error">{{ errores.correo }}</div>
        </div>
        <button type="submit" class="btn btn-primario btn-bloque" :disabled="ocupado">
          {{ ocupado ? "Enviando…" : "Enviar código" }}
        </button>
      </form>

      <form v-else novalidate @submit.prevent="cambiar">
        <p class="intro">
          Si <b>{{ form.correo }}</b> tiene cuenta, ahí llegó un código de 6 dígitos. Si no lo ves, revisa la carpeta de
          spam.
        </p>
        <div v-if="errorGeneral" class="error-general" role="alert">{{ errorGeneral }}</div>
        <div class="campo">
          <label for="codigo">Código</label>
          <input
            id="codigo"
            v-model="form.codigo"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="6"
          />
          <div v-if="errores.codigo" class="error">{{ errores.codigo }}</div>
        </div>
        <div class="campo">
          <label for="password">Contraseña nueva</label>
          <input id="password" v-model="form.password" type="password" autocomplete="new-password" />
          <div v-if="errores.password" class="error">{{ errores.password }}</div>
          <div v-else class="ayuda">Al menos 8 caracteres, que no sea solo números ni muy común.</div>
        </div>
        <div class="fila-botones">
          <button type="button" class="btn btn-secundario" :disabled="espera > 0 || ocupado" @click="pedirCodigo">
            {{ espera > 0 ? `Reenviar (${espera} s)` : "Reenviar código" }}
          </button>
          <button type="submit" class="btn btn-primario" :disabled="ocupado">
            {{ ocupado ? "Guardando…" : "Cambiar contraseña" }}
          </button>
        </div>
      </form>
    </div>
    <p class="pie-acceso"><RouterLink :to="{ name: 'entrar' }">Volver a Entrar</RouterLink></p>
  </main>
</template>
