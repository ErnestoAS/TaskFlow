import type { Estatus, Permiso, Prioridad, Tarjeta } from "./tipos";

export const ESTATUS: [Estatus, string][] = [
  ["pendiente", "Pendiente"],
  ["en_curso", "En curso"],
  ["finalizada", "Finalizada"],
];
export const PRIORIDADES: [Prioridad, string][] = [
  ["baja", "Baja"],
  ["media", "Media"],
  ["alta", "Alta"],
  ["urgente", "Urgente"],
];
export const PERMISOS: [Permiso, string][] = [
  ["crear", "Crear"],
  ["editar", "Editar"],
  ["cambiar_estatus", "Cambiar estatus"],
  ["eliminar", "Eliminar"],
  ["gestionar_tipos", "Gestionar tipos"],
];
/** Colores sugeridos para tipos (docs/identidad-visual.md). El usuario puede elegir otro. */
export const MUESTRAS = ["#6366f1", "#8b5cf6", "#0ea5e9", "#64748b", "#ec4899", "#78716c"];

export const nombreEstatus = (e: Estatus) => ESTATUS.find(([k]) => k === e)?.[1] ?? e;
export const nombrePrioridad = (p: Prioridad) => PRIORIDADES.find(([k]) => k === p)?.[1] ?? p;
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

export function fechaHora(iso: string): string {
  const f = new Date(iso);
  const hh = String(f.getHours()).padStart(2, "0");
  const mm = String(f.getMinutes()).padStart(2, "0");
  return `${f.getDate()} ${MESES[f.getMonth()]} ${f.getFullYear()} · ${hh}:${mm}`;
}

export type EstadoFecha = { clase: "vencida" | "por-vencer" | "fecha"; texto: string } | null;

export function estadoFecha(t: Pick<Tarjeta, "fecha_fin" | "estatus">): EstadoFecha {
  if (!t.fecha_fin) return null;
  const dias = diasHasta(t.fecha_fin);
  if (t.estatus !== "finalizada") {
    if (dias < 0) return { clase: "vencida", texto: `Vencida · ${fechaCorta(t.fecha_fin)}` };
    if (dias === 0) return { clase: "por-vencer", texto: "Vence hoy" };
    if (dias === 1) return { clase: "por-vencer", texto: "Vence mañana" };
  }
  return { clase: "fecha", texto: fechaCorta(t.fecha_fin) };
}

export const esVencida = (t: Pick<Tarjeta, "fecha_fin" | "estatus">) =>
  !!t.fecha_fin && t.estatus !== "finalizada" && diasHasta(t.fecha_fin) < 0;
