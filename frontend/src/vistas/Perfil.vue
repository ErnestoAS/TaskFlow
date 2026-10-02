<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";

import { api, ErrorApi, RAIZ, mensajeDeError } from "../api";
import Avatar from "../componentes/Avatar.vue";
import AvisoInstalacion from "../componentes/AvisoInstalacion.vue";
import Cabecera from "../componentes/Cabecera.vue";
import Hoja from "../componentes/Hoja.vue";
import { instalacion } from "../instalacion";
import { olvidarProyectos } from "../proyectos";
import { salir, sesion } from "../sesion";
import type { Usuario } from "../tipos";
import { avisar } from "../ui";

const router = useRouter();
const hoja = ref<"nombre" | "password" | null>(null);
const errores = ref<Record<string, string>>({});
const ocupado = ref(false);
const datos = reactive({ nombre: "", primer_apellido: "", segundo_apellido: "", actual: "", nueva: "" });

async function abrir(cual: "nombre" | "password") {
  errores.value = {};
  Object.assign(datos, { nombre: "", primer_apellido: "", segundo_apellido: "", actual: "", nueva: "" });
  if (cual === "nombre") {
    // yo/ trae nombre y apellidos por separado; `nombre` en el resto de la API es el completo.
    const yo = await api<Usuario>("yo/").catch(() => sesion.usuario);
    datos.nombre = yo?.nombre_pila ?? yo?.nombre ?? "";
    datos.primer_apellido = yo?.primer_apellido ?? "";
    datos.segundo_apellido = yo?.segundo_apellido ?? "";
  }
  hoja.value = cual;
}

async function guardar() {
  errores.value = {};
  ocupado.value = true;
  try {
    if (hoja.value === "nombre") {
      const { nombre, primer_apellido, segundo_apellido } = datos;
      sesion.usuario = await api<Usuario>("yo/", "PATCH", { nombre, primer_apellido, segundo_apellido });
      avisar("Se guardó tu nombre.");
    } else {
      await api("yo/password/", "POST", { actual: datos.actual, nueva: datos.nueva });
      avisar("Se cambió tu contraseña.");
    }
    hoja.value = null;
  } catch (e) {
    errores.value = e instanceof ErrorApi && Object.keys(e.campos).length ? e.campos : { general: mensajeDeError(e) };
  } finally {
    ocupado.value = false;
  }
}

async function cerrarSesion() {
  await salir();
  olvidarProyectos();
  await router.replace({ name: "entrar" });
}
</script>

<template>
  <Cabecera titulo="TaskFlow" sub="Perfil" />
  <main v-if="sesion.usuario" class="contenido" style="max-width: 640px">
    <AvisoInstalacion />
    <div class="tarjeta-blanca" style="padding: 16px">
      <div class="persona" style="border: 0">
        <Avatar :usuario="sesion.usuario" />
        <div class="nombre">
          <b>{{ sesion.usuario.nombre }}</b><small>{{ sesion.usuario.correo }}</small>
        </div>
      </div>
    </div>
    <div class="seccion-titulo">Cuenta</div>
    <div class="tarjeta-blanca lista-acciones">
      <button @click="abrir('nombre')"><span class="nombre">Cambiar nombre</span></button>
      <button @click="abrir('password')"><span class="nombre">Cambiar contraseña</span></button>
      <a v-if="!instalacion.instalada" :href="RAIZ"
        ><span class="nombre">Instalar la app<small>Pasos en la página de instalación</small></span></a
      >
    </div>
    <div style="margin-top: 18px">
      <button class="btn btn-secundario btn-bloque" @click="cerrarSesion">Cerrar sesión</button>
    </div>
  </main>

  <Hoja v-if="hoja" :titulo="hoja === 'nombre' ? 'Cambiar nombre' : 'Cambiar contraseña'" @cerrar="hoja = null">
    <form novalidate @submit.prevent="guardar">
      <div v-if="errores.general" class="error-general" role="alert">{{ errores.general }}</div>
      <template v-if="hoja === 'nombre'">
        <div class="campo">
          <label for="p-nombre">Nombre</label>
          <input id="p-nombre" v-model="datos.nombre" type="text" autocomplete="given-name" />
          <div v-if="errores.nombre" class="error">{{ errores.nombre }}</div>
        </div>
        <div class="campo">
          <label for="p-primer-apellido">Primer apellido</label>
          <input id="p-primer-apellido" v-model="datos.primer_apellido" type="text" autocomplete="family-name" />
          <div v-if="errores.primer_apellido" class="error">{{ errores.primer_apellido }}</div>
        </div>
        <div class="campo">
          <label for="p-segundo-apellido">Segundo apellido <span style="text-transform: none; font-weight: 400">(opcional)</span></label>
          <input id="p-segundo-apellido" v-model="datos.segundo_apellido" type="text" autocomplete="off" />
        </div>
      </template>
      <template v-else>
        <div class="campo">
          <label for="p-actual">Contraseña actual</label>
          <input id="p-actual" v-model="datos.actual" type="password" autocomplete="current-password" />
          <div v-if="errores.actual" class="error">{{ errores.actual }}</div>
        </div>
        <div class="campo">
          <label for="p-nueva">Contraseña nueva</label>
          <input id="p-nueva" v-model="datos.nueva" type="password" autocomplete="new-password" />
          <div v-if="errores.nueva" class="error">{{ errores.nueva }}</div>
        </div>
      </template>
      <div class="fila-botones">
        <button type="button" class="btn btn-secundario" @click="hoja = null">Cancelar</button>
        <button type="submit" class="btn btn-primario" :disabled="ocupado">Guardar</button>
      </div>
    </form>
  </Hoja>
</template>
