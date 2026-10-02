import { reactive } from "vue";

import { api } from "./api";
import type { Usuario } from "./tipos";

export const sesion = reactive({
  usuario: null as Usuario | null,
  registroAbierto: true,
  cargada: false,
});

export async function cargarSesion(): Promise<void> {
  try {
    // auth/csrf/ deja la cookie CSRF y trae el usuario de la sesión (o null) en una sola llamada.
    const info = await api<{ registro_abierto: boolean; usuario: Usuario | null }>("auth/csrf/");
    sesion.registroAbierto = info.registro_abierto;
    sesion.usuario = info.usuario;
  } catch (e) {
    // Sin conexión y sin caché: se muestra «Entrar»; la sesión del servidor sigue intacta.
    console.warn(e);
    sesion.usuario = null;
  } finally {
    sesion.cargada = true;
  }
}

export async function entrar(correo: string, password: string): Promise<void> {
  sesion.usuario = await api<Usuario>("auth/entrar/", "POST", { correo, password });
}

export async function salir(): Promise<void> {
  await api("auth/salir/", "POST").catch(() => undefined);
  sesion.usuario = null;
  // Que la siguiente persona en este dispositivo no vea datos de la anterior sin conexión.
  if ("caches" in window) await caches.delete("taskflow-datos").catch(() => undefined);
}
