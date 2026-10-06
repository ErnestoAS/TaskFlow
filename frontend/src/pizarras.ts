/** Pizarras del usuario: las usan la vista «Mis pizarras» y la barra lateral. */
import { reactive } from "vue";

import { api } from "./api";
import type { PizarraResumen } from "./tipos";

export const misPizarras = reactive({
  lista: [] as PizarraResumen[],
  cargadas: false,
});

export async function recargarPizarras(): Promise<void> {
  misPizarras.lista = await api<PizarraResumen[]>("pizarras/");
  misPizarras.cargadas = true;
}

export function olvidarPizarras(): void {
  misPizarras.lista = [];
  misPizarras.cargadas = false;
}
