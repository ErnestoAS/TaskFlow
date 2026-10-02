/**
 * Instalación de la PWA. `beforeinstallprompt` (Chrome, Edge, Android) puede llegar antes de que
 * exista la vista, así que se captura al importar este módulo desde main.ts. En iOS no existe:
 * se muestran los pasos de Safari.
 */
import { reactive } from "vue";

interface EventoInstalacion extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const CLAVE = "taskflow.instalacion-descartada";

function leerDescarte(): boolean {
  try {
    return localStorage.getItem(CLAVE) === "1";
  } catch {
    return false;
  }
}

export const instalacion = reactive({
  evento: null as EventoInstalacion | null,
  instalada:
    window.matchMedia("(display-mode: standalone)").matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true,
  descartada: leerDescarte(),
  // Llegó desde la portada con «Abrir e instalar»: el aviso se muestra aunque se haya descartado.
  pedida: new URLSearchParams(location.search).has("instalar"),
  esIOS:
    /iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1),
});

window.addEventListener("beforeinstallprompt", (evento) => {
  evento.preventDefault();
  instalacion.evento = evento as EventoInstalacion;
});
window.addEventListener("appinstalled", () => {
  instalacion.instalada = true;
  instalacion.evento = null;
});

export async function instalar(): Promise<void> {
  if (!instalacion.evento) return;
  await instalacion.evento.prompt();
  const { outcome } = await instalacion.evento.userChoice;
  if (outcome === "accepted") instalacion.instalada = true;
  instalacion.evento = null;
}

export function descartar(): void {
  instalacion.descartada = true;
  instalacion.pedida = false;
  try {
    localStorage.setItem(CLAVE, "1");
  } catch {
    /* sin almacenamiento: solo dura esta visita */
  }
}
