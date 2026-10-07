/**
 * Cliente de /api/v1/. Mismo origen que Django: sesión por cookie y X-CSRFToken en las mutaciones.
 *
 * La raíz se calcula de la URL: en producción la app vive en /taskflow/app/ y la API en
 * /taskflow/api/v1/; en local, /app/ y /api/v1/ (§5). Así la misma build sirve en ambos.
 */

const posicion = location.pathname.indexOf("/app/");
export const RAIZ = posicion >= 0 ? location.pathname.slice(0, posicion + 1) : "/";
const API = `${RAIZ}api/v1/`;
const COOKIE_CSRF = "taskflow_csrftoken";

export class ErrorApi extends Error {
  constructor(
    public estado: number,
    public datos: Record<string, unknown> | null,
  ) {
    super(mensajeDe(datos) ?? `Error ${estado}`);
  }

  /** Errores por campo, p. ej. {titulo: "Escribe un título."}. */
  get campos(): Record<string, string> {
    const salida: Record<string, string> = {};
    for (const [campo, valor] of Object.entries(this.datos ?? {})) {
      if (campo === "detalle") continue;
      salida[campo] = Array.isArray(valor) ? valor.join(" ") : String(valor);
    }
    return salida;
  }
}

function mensajeDe(datos: Record<string, unknown> | null): string | null {
  if (!datos) return null;
  if (typeof datos.detalle === "string") return datos.detalle;
  const mensajes = Object.values(datos).flat().filter((v) => typeof v === "string");
  return mensajes.length ? mensajes.join(" ") : null;
}

function leerCookie(nombre: string): string | undefined {
  const par = document.cookie.split("; ").find((c) => c.startsWith(`${nombre}=`));
  return par ? decodeURIComponent(par.split("=")[1]) : undefined;
}

async function tokenCsrf(): Promise<string | undefined> {
  if (!leerCookie(COOKIE_CSRF)) await fetch(`${API}auth/csrf/`, { credentials: "same-origin" });
  return leerCookie(COOKIE_CSRF);
}

type Metodo = "GET" | "POST" | "PATCH" | "DELETE";

export async function api<T = unknown>(ruta: string, metodo: Metodo = "GET", datos?: unknown): Promise<T> {
  const cabeceras: Record<string, string> = { Accept: "application/json" };
  if (metodo !== "GET") {
    cabeceras["Content-Type"] = "application/json";
    const token = await tokenCsrf();
    if (token) cabeceras["X-CSRFToken"] = token;
  }
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API}${ruta}`, {
      method: metodo,
      credentials: "same-origin",
      headers: cabeceras,
      body: datos === undefined ? undefined : JSON.stringify(datos),
    });
  } catch {
    throw new ErrorApi(0, { detalle: "Sin conexión. Revisa tu internet e inténtalo de nuevo." });
  }
  if (respuesta.status === 204) return null as T;
  const cuerpo = await respuesta.json().catch(() => null);
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, cuerpo);
  return cuerpo as T;
}

/** Ruta completa de la API, para enlaces (descargar un adjunto): funciona bajo /taskflow/. */
export const rutaApi = (ruta: string) => `${API}${ruta}`;

/** POST multipart (adjuntos): sin Content-Type, que lo pone el navegador con su separador. */
export async function subir<T = unknown>(ruta: string, datos: FormData): Promise<T> {
  const cabeceras: Record<string, string> = { Accept: "application/json" };
  const token = await tokenCsrf();
  if (token) cabeceras["X-CSRFToken"] = token;
  let respuesta: Response;
  try {
    respuesta = await fetch(`${API}${ruta}`, { method: "POST", credentials: "same-origin", headers: cabeceras, body: datos });
  } catch {
    throw new ErrorApi(0, { detalle: "Sin conexión. Revisa tu internet e inténtalo de nuevo." });
  }
  const cuerpo = await respuesta.json().catch(() => null);
  if (respuesta.status === 413) throw new ErrorApi(413, { archivo: "El archivo es demasiado grande." });
  if (!respuesta.ok) throw new ErrorApi(respuesta.status, cuerpo);
  return cuerpo as T;
}

export function mensajeDeError(error: unknown, respaldo = "Ocurrió un error. Inténtalo de nuevo."): string {
  return error instanceof ErrorApi ? error.message : respaldo;
}
