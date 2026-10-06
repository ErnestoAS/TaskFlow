import type { Permiso, Prioridad, Tarjeta } from "./tipos";

export const PRIORIDADES: [Prioridad, string][] = [
  ["baja", "Baja"],
  ["media", "Media"],
  ["alta", "Alta"],
  ["urgente", "Urgente"],
];
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

export const nombrePrioridad = (p: Prioridad) => PRIORIDADES.find(([k]) => k === p)?.[1] ?? p;
export const plural = (n: number, uno: string, varios = `${uno}s`) => `${n} ${n === 1 ? uno : varios}`;

const MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];

/** «2026-10-15» → Date local (sin desfase de zona). */
export function fechaLocal(iso: string): Date {
  const [a, m, d] = iso.split("-").map(Number);
  return new Date(a, m - 1, d);
}

/** Hoy como «AAAA-MM-DD» en la zona del teléfono (para el valor por omisión de los formularios). */
export function hoyIso(): string {
  const h = new Date();
  return `${h.getFullYear()}-${String(h.getMonth() + 1).padStart(2, "0")}-${String(h.getDate()).padStart(2, "0")}`;
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

/** Una tarjeta en lista de cierre cuenta como terminada: nunca sale vencida (§4.6). */
export function estadoFecha(t: Pick<Tarjeta, "fecha_fin" | "en_cierre">): EstadoFecha {
  if (!t.fecha_fin) return null;
  const dias = diasHasta(t.fecha_fin);
  if (!t.en_cierre) {
    if (dias < 0) return { clase: "vencida", texto: `Vencida · ${fechaCorta(t.fecha_fin)}` };
    if (dias === 0) return { clase: "por-vencer", texto: "Vence hoy" };
    if (dias === 1) return { clase: "por-vencer", texto: "Vence mañana" };
  }
  return { clase: "fecha", texto: fechaCorta(t.fecha_fin) };
}

export const esVencida = (t: Pick<Tarjeta, "fecha_fin" | "en_cierre">) =>
  !!t.fecha_fin && !t.en_cierre && diasHasta(t.fecha_fin) < 0;
