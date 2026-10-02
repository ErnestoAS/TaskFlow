/** Avisos breves (toast) y confirmaciones destructivas: un solo mecanismo para toda la app. */
import { reactive } from "vue";

export const ui = reactive({
  aviso: "" as string,
  confirmacion: null as null | { mensaje: string; boton: string; resolver: (ok: boolean) => void },
});

let temporizador: ReturnType<typeof setTimeout> | undefined;

/** Texto en pasado, una oración, sin signos de exclamación (CLAUDE.md, §Mensajes). */
export function avisar(texto: string): void {
  ui.aviso = texto;
  clearTimeout(temporizador);
  temporizador = setTimeout(() => (ui.aviso = ""), 2600);
}

/** Pregunta que nombra lo afectado y advierte la consecuencia. Nunca window.confirm(). */
export function confirmar(mensaje: string, boton: string): Promise<boolean> {
  return new Promise((resolver) => {
    ui.confirmacion = {
      mensaje,
      boton,
      resolver: (ok) => {
        ui.confirmacion = null;
        resolver(ok);
      },
    };
  });
}
