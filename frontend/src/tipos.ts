/** Lo que devuelve /api/v1/ (apps/api/representacion.py). */

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
  n_actividades?: number;
}

/** Persona que pide actividades sin ser miembro de la pizarra (Etapa 3.8). */
export interface Solicitante {
  id: number;
  nombre: string;
  n_actividades?: number;
}

/** «Solicitada por» de una actividad: un miembro o un externo del catálogo de la pizarra. */
export interface SolicitanteDeActividad {
  tipo: "miembro" | "externo";
  id: number;
  nombre: string;
}

/** Lo que se elige en el combo «Solicitada por»; «nuevo» se crea al guardar la actividad. */
export type EleccionSolicitante = SolicitanteDeActividad | { tipo: "nuevo"; id?: undefined; nombre: string };

/** Archivo de una actividad (Etapa 3.8). Se descarga con `rutaApi(`adjuntos/${id}/`)`. */
export interface Adjunto {
  id: number;
  nombre: string;
  tamano: number;
  tipo: string;
  subido_por: Usuario | null;
  creado_en: string;
}

/** Columna de una pizarra con nombre libre (§4.6). Ninguna significa «terminado» por sí misma. */
export interface Lista {
  id: number;
  nombre: string;
  posicion: number;
  n_actividades?: number;
}

/** Resumen de tamaño fijo de «Mis pizarras»: no crece con el número de listas. */
export interface Conteos {
  actividades: number;
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
  solicitantes: Solicitante[];
  /** Bytes usados por los adjuntos de la pizarra, el tope y el máximo por archivo. */
  adjuntos_espacio: { usado: number; limite: number; max_archivo: number };
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
  /** Convertido en actividad y su actividad tiene lista de terminado: se palomea solo. */
  automatico: boolean;
  actividad: { id: number; titulo: string; lista: number; lista_nombre: string } | null;
}

export interface Actividad {
  id: number;
  pizarra: number;
  pizarra_nombre: string;
  lista: number;
  lista_nombre: string;
  /** «Lo que llega a esta lista cuenta como terminado» para las actividades de su checklist. */
  lista_terminado: number | null;
  posicion: number;
  titulo: string;
  descripcion: string;
  /** «Solicitada el» (Etapa 3.8): opcional. */
  fecha_solicitud: string | null;
  /** «Mover a [lista] al completar» la checklist (Etapa 3.8). */
  lista_al_completar: number | null;
  fecha_fin: string | null;
  asignados: Usuario[];
  tipos: number[];
  solicitante: SolicitanteDeActividad | null;
  creada_por: Usuario | null;
  creado_en: string;
  checklist_conteo: { hechos: number; total: number } | null;
  viene_de: { id: number; titulo: string; elemento: string } | null;
  n_adjuntos: number;
  /** Solo en el detalle. */
  checklist?: ElementoChecklist[];
  historial?: Movimiento[];
  adjuntos?: Adjunto[];
}
