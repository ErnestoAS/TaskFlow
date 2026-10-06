import { createRouter, createWebHashHistory, type RouteRecordRaw } from "vue-router";

import { sesion } from "./sesion";

const rutas: RouteRecordRaw[] = [
  { path: "/", redirect: { name: "pizarras" } },
  { path: "/pizarras", name: "pizarras", component: () => import("./vistas/Pizarras.vue") },
  { path: "/pizarras/:id", name: "tablero", component: () => import("./vistas/Tablero.vue"), props: (r) => ({ id: Number(r.params.id) }) },
  { path: "/pizarras/:id/ajustes", name: "ajustes", component: () => import("./vistas/Ajustes.vue"), props: (r) => ({ id: Number(r.params.id) }) },
  // Enlaces guardados de antes del cambio de nombre (2026-10-05).
  { path: "/proyectos", redirect: { name: "pizarras" } },
  { path: "/proyectos/:id", redirect: (r) => ({ name: "tablero", params: { id: r.params.id } }) },
  { path: "/proyectos/:id/ajustes", redirect: (r) => ({ name: "ajustes", params: { id: r.params.id } }) },
  { path: "/mis-tarjetas", name: "mis-tarjetas", component: () => import("./vistas/MisTarjetas.vue") },
  { path: "/perfil", name: "perfil", component: () => import("./vistas/Perfil.vue") },
  { path: "/entrar", name: "entrar", component: () => import("./vistas/Entrar.vue"), meta: { publica: true, soloAnonimo: true } },
  { path: "/registro", name: "registro", component: () => import("./vistas/Registro.vue"), meta: { publica: true, soloAnonimo: true } },
  // ?correo= de la cuenta por confirmar; ?siguiente= como en Entrar.
  { path: "/verificar", name: "verificar", component: () => import("./vistas/Verificar.vue"), meta: { publica: true, soloAnonimo: true } },
  { path: "/recuperar", name: "recuperar", component: () => import("./vistas/Recuperar.vue"), meta: { publica: true, soloAnonimo: true } },
  // Abierta con o sin sesión: quien no tiene cuenta la crea desde aquí (§4.5).
  { path: "/invitacion/:token", name: "invitacion", component: () => import("./vistas/Invitacion.vue"), props: true, meta: { publica: true } },
  { path: "/:pathMatch(.*)*", redirect: { name: "pizarras" } },
];

// Rutas con # (createWebHashHistory): la app vive bajo un prefijo que cambia según el servidor
// (/app/ o /taskflow/app/) y así el servidor solo tiene que servir index.html (§5).
export const router = createRouter({
  history: createWebHashHistory(),
  routes: rutas,
  scrollBehavior: () => ({ top: 0 }),
});

router.beforeEach((destino) => {
  if (!destino.meta.publica && !sesion.usuario) {
    return { name: "entrar", query: destino.fullPath !== "/pizarras" ? { siguiente: destino.fullPath } : {} };
  }
  if (destino.meta.soloAnonimo && sesion.usuario) return { name: "pizarras" };
  return true;
});
