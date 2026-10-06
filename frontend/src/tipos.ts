/** Lo que devuelve /api/v1/ (apps/api/representacion.py). */

export type Prioridad = "baja" | "media" | "alta" | "urgente";
export type Permiso = "crear" | "editar" | "mover" | "eliminar" | "gestionar_listas" | "gestionar_tipos";
export type Permisos = Record<Permiso, boolean>;

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  iniciales: string;
  /** Solo en yo/: nombre y apellidos por separado. */
  nombre_pila?: string;
  primer_apellido?: string;
  segundo_apellido?: string;
}

export interface Tipo {
  id: number;
  nombre: string;
  descripcion: string;
  color: string;
  n_tarjetas?: number;
}

/** Columna de una pizarra con nombre libre (§4.6). De cierre: lo que llega aquí está terminado. */
export interface Lista {
  id: number;
  nombre: string;
  posicion: number;
  es_cierre: boolean;
  n_tarjetas?: number;
}

/** Resumen de tamaño fijo de «Mis pizarras»: no crece con el número de listas. */
export interface Conteos {
  tarjetas: number;
  listas: number;
  mias: number;
  vencidas: number;
}

export interface PizarraResumen {
  id: number;
  nombre: string;
  archivada: boolean;
  rol: "dueno" | "miembro" | null;
  dueno: Usuario | null;
  miembros: Usuario[];
  conteos: Conteos;
  permisos: Permisos;
}

export interface Miembro {
  usuario: Usuario;
  rol: "dueno" | "miembro";
  permisos: Permisos;
}

export interface Invitacion {
  id: number;
  correo: string;
  enviada_en: string;
  veces_enviada: number;
}

export interface PizarraDetalle extends Omit<PizarraResumen, "miembros"> {
  miembros: Miembro[];
  listas: Lista[];
  tipos: Tipo[];
  invitaciones: Invitacion[];
}

/** Una entrada del historial: creación (de = null), movimiento entre listas o una nota. */
export interface Movimiento {
  fecha: string;
  usuario: Usuario | null;
  de: string | null;
  a: string | null;
  nota: string | null;
}

export interface ElementoChecklist {
  id: number;
  texto: string;
  hecho: boolean;
  /** Convertido en tarjeta y con lista elegida: se palomea solo. */
  automatico: boolean;
  tarjeta: { id: number; titulo: string; lista: number; lista_nombre: string } | null;
  lista_terminado: { id: number; nombre: string } | null;
}

export interface Tarjeta {
  id: number;
  pizarra: number;
  pizarra_nombre: string;
  lista: number;
  lista_nombre: string;
  /** Está en una lista de cierre: no sale vencida ni en «Mis tarjetas». */
  en_cierre: boolean;
  posicion: number;
  titulo: string;
  descripcion: string;
  prioridad: Prioridad;
  fecha_inicio: string;
  fecha_fin: string | null;
  asignados: Usuario[];
  tipos: number[];
  creada_por: Usuario | null;
  creado_en: string;
  checklist_conteo: { hechos: number; total: number } | null;
  viene_de: { id: number; titulo: string; elemento: string } | null;
  /** Solo en el detalle. */
  checklist?: ElementoChecklist[];
  historial?: Movimiento[];
}
