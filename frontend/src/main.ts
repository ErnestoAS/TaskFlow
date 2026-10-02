// Tipografía y paleta: los mismos archivos que usan las plantillas de Django (portada), para
// que haya una sola fuente de colores y la Inter vaya empaquetada (docs/identidad-visual.md).
import "../../static/css/fuentes.css";
import "../../static/css/tema.css";
import "./estilos.css";

import { createApp } from "vue";

import App from "./App.vue";
import "./instalacion";
import { router } from "./router";
import { cargarSesion } from "./sesion";

cargarSesion().finally(() => {
  createApp(App).use(router).mount("#app");
});
