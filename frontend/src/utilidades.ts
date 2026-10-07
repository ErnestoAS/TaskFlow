import type { Actividad, Permiso } from "./tipos";

export const PERMISOS: [Permiso, string][] = [
  ["crear", "Crear"],
  ["editar", "Editar"],
  ["mover", "Mover"],
  ["eliminar", "Eliminar"],
  ["gestionar_listas", "Gestionar listas"],
  ["gestionar_tipos", "Gestionar tipos"],
];
/** Colores sugeridos para tipos (docs/identidad-visual.md). El usuario puede elegir otro. */
export const MUESTRAS = ["#6366f1", "#8b5cf6", "#0ea5e9", "#64748b", "#ec4899", "#78716c"];

/** Largo máximo de un elemento de la checklist (lo valida el servidor; Etapa 3.8: antes 200). */
export const MAX_TEXTO_ELEMENTO = 400;
/** Largo máximo del título de una actividad. */
export const MAX_TITULO = 200;

/**
 * Parte un texto largo en título y resto (al convertir un elemento de la checklist): corta en el
 * último espacio antes del tope para no partir una palabra, salvo que eso dejara un título muy
 * corto. El resto va a la descripción.
 */
export function partirTitulo(texto: string, tope = MAX_TITULO): [string, string] {
  if (texto.length <= tope) return [texto, ""];
  let corte = texto.lastIndexOf(" ", tope);
  if (corte < tope * 0.6) corte = tope;
  return [texto.slice(0, corte).trim(), texto.slice(corte).trim()];
}

/** La checklist como texto para pegar en un correo o un chat: «✓» hecho, «•» pendiente. */
export const textoChecklist = (elementos: { texto: string; hecho: boolean }[]) =>
  elementos.map((e) => `${e.hecho ? "✓" : "•"} ${e.texto}`).join("\n");

/** Al portapapeles; si el navegador no deja (sin HTTPS o sin permiso), con un textarea oculto. */
export async function copiarTexto(texto: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(texto);
      return;
    } catch {
      /* se intenta abajo */
    }
  }
  const area = document.createElement("textarea");
  area.value = texto;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  const ok = document.execCommand("copy");
  area.remove();
  if (!ok) throw new Error("No se pudo copiar.");
}

export const plural = (n: number, uno: string, varios = `${uno}s`) => `${n} ${n === 1 ? uno : varios}`;

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** «2026-10-15» → Date local (sin desfase de zona). */
export function fechaLocal(iso: string): Date {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

export function diasHasta(iso: string): number {
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return Math.round((fechaLocal(iso).getTime() - hoy.getTime()) / 864e5);
}

export const fechaCorta = (iso: string) => {
  const f = fechaLocal(iso);
  return `${f.getDate()} ${MESES[f.getMonth()]}`;
};

export const fechaLarga = (iso: string) => {
  const f = fechaLocal(iso);
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()}`;
};

export function fechaHora(iso: string): string {
  const f = new Date(iso);
  const hh = String(f.getHours()).padStart(2, "0");
  const mm = String(f.getMinutes()).padStart(2, "0");
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()} · ${hh}:${mm}`;
}

export type EstadoFecha = { clase: "vencida" | "por-vencer" | "fecha"; texto: string } | null;

/** Sin listas de cierre (2026-10-06): con fecha límite pasada sale vencida, esté en la lista que esté. */
export function estadoFecha(t: Pick<Actividad, "fecha_fin">): EstadoFecha {
  if (!t.fecha_fin) return null;
  const dias = diasHasta(t.fecha_fin);
  if (dias < 0) return { clase: "vencida", texto: `Vencida · ${fechaCorta(t.fecha_fin)}` };
  if (dias === 0) return { clase: "por-vencer", texto: "Vence hoy" };
  if (dias === 1) return { clase: "por-vencer", texto: "Vence mañana" };
  return { clase: "fecha", texto: fechaCorta(t.fecha_fin) };
}

export const esVencida = (t: Pick<Actividad, "fecha_fin">) => !!t.fecha_fin && diasHasta(t.fecha_fin) < 0;
