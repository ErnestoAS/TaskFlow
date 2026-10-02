/** Lo que devuelve /api/v1/ (apps/api/representacion.py). */

export type Estatus = "pendiente" | "en_curso" | "finalizada";
export type Prioridad = "baja" | "media" | "alta" | "urgente";
export type Permiso = "crear" | "editar" | "cambiar_estatus" | "eliminar" | "gestionar_tipos";
export type Permisos = Record<Permiso, boolean>;

export interface Usuario {
  id: number;
  nombre: string;
  correo: string;
  iniciales: string;
  /** Solo en yo/: nombre y apellidos por separado. */
  nombre_pila?: string;
  apellidos?: string;
}

export interface Tipo {
  id: number;
  nombre: string;
  descripcion: string;
  color: string;
  n_tarjetas?: number;
}

export interface Conteos {
  pendiente: number;
  en_curso: number;
  finalizada: number;
  vencidas: number;
}

export interface ProyectoResumen {
  id: number;
  nombre: string;
  archivado: boolean;
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

export interface ProyectoDetalle extends Omit<ProyectoResumen, "miembros"> {
  miembros: Miembro[];
  tipos: Tipo[];
  invitaciones: Invitacion[];
}

export interface Cambio {
  fecha: string;
  usuario: Usuario | null;
  de: Estatus | null;
  a: Estatus;
}

export interface Tarjeta {
  id: number;
  proyecto: number;
  proyecto_nombre: string;
  titulo: string;
  descripcion: string;
  estatus: Estatus;
  prioridad: Prioridad;
  fecha_fin: string | null;
  asignados: Usuario[];
  tipos: number[];
  creada_por: Usuario | null;
  creado_en: string;
  historial?: Cambio[];
}
