/** Lista de proyectos del usuario: la usan la vista Proyectos y la barra lateral. */
import { reactive } from "vue";

import { api } from "./api";
import type { ProyectoResumen } from "./tipos";

export const misProyectos = reactive({
  lista: [] as ProyectoResumen[],
  cargados: false,
});

export async function recargarProyectos(): Promise<void> {
  misProyectos.lista = await api<ProyectoResumen[]>("proyectos/");
  misProyectos.cargados = true;
}

export function olvidarProyectos(): void {
  misProyectos.lista = [];
  misProyectos.cargados = false;
}
