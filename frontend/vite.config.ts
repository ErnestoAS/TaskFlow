import { fileURLToPath, URL } from "node:url";

import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// Django (servicio `web` del compose) atiende /api en desarrollo.
const django = process.env.DJANGO_URL ?? "http://web:8000";

export default defineConfig({
  // Rutas relativas: la misma build funciona en /app/ (local) y en /taskflow/app/ (producción).
  // Por eso el router usa # (§5): el servidor solo sirve /app/index.html.
  base: "./",
  build: { outDir: "../pwa/app", emptyOutDir: true },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    // tema.css vive en ../static/css (compartido con las plantillas de Django).
    fs: { allow: [".."] },
    proxy: { "/api": { target: django, changeOrigin: false } },
  },
  plugins: [
    vue(),
    VitePWA({
      registerType: "prompt",
      injectRegister: false,
      manifest: {
        name: "TaskFlow",
        short_name: "TaskFlow",
        description: "Organiza las actividades de tu equipo en tarjetas.",
        lang: "es-MX",
        start_url: "./",
        scope: "./",
        display: "standalone",
        theme_color: "#172554",
        background_color: "#f5f7fa",
        icons: [
          { src: "iconos/icono-192.png", sizes: "192x192", type: "image/png" },
          { src: "iconos/icono-512.png", sizes: "512x512", type: "image/png" },
          { src: "iconos/icono-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,svg,png,woff2}"],
        navigateFallback: null,
        runtimeCaching: [
          {
            // Sin conexión (§5): se ven los últimos proyectos y tarjetas cargados. auth/csrf/ entra
            // para saber quién tenía la sesión; al salir se borra esta caché (sesion.ts).
            urlPattern: ({ url, request }) =>
              request.method === "GET" && /\/api\/v1\/(auth\/csrf|yo|proyectos|tarjetas)\b/.test(url.pathname),
            handler: "NetworkFirst",
            options: {
              cacheName: "taskflow-datos",
              networkTimeoutSeconds: 4,
              expiration: { maxEntries: 200, maxAgeSeconds: 7 * 24 * 3600 },
              cacheableResponse: { statuses: [200] },
            },
          },
        ],
      },
    }),
  ],
});
