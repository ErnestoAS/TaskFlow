---
name: taskflow-dev
description: Flujo de desarrollo de TaskFlow en Docker (levantar stack, migraciones, pruebas, lint, crear apps, agregar dependencias, build de producción) y definición de terminado. Úsala antes de ejecutar comandos de Django, agregar modelos, vistas o endpoints, o cambiar la configuración de Docker.
---

# Desarrollo de TaskFlow

Todo se ejecuta **dentro de Docker**; no hay entorno virtual local. Dependencias con **uv**.

## Comandos

| Tarea | Comando |
| --- | --- |
| Levantar (migra al iniciar) | `docker compose up -d` → http://localhost:8030 (portada `/`, app `/app/`, admin `/django-admin/`) |
| Compilar la PWA (la sirve Django en `/app/`) | `docker compose run --rm frontend sh -c "npm ci && npm run build"` (deja `pwa/app/`, no se versiona; `run` no ejecuta el `npm install` del servicio y el volumen de `node_modules` empieza vacío) |
| PWA con recarga en caliente | `docker compose --profile frontend up` → http://localhost:5173/app/ (Vite reenvía `/api` a `web`) |
| Revisar tipos de la PWA | `docker compose run --rm frontend sh -c "npm ci && npm run typecheck"` |
| Dependencia de la PWA | `docker compose run --rm frontend npm install <paquete>` (actualiza `frontend/package-lock.json`) |
| Logs | `docker compose logs -f web` |
| Superusuario | `docker compose exec web python manage.py createsuperuser` |
| Shell | `docker compose exec web python manage.py shell` |
| Migraciones | `docker compose exec web python manage.py makemigrations <app>` y `... migrate` |
| Verificar migraciones faltantes | `docker compose exec web python manage.py makemigrations --check --dry-run` |
| Pruebas | `docker compose exec web pytest` |
| Lint / formato | `docker compose exec web ruff check .` · `docker compose exec web ruff format .` |
| Agregar dependencia | editar `pyproject.toml` → `docker compose run --rm --no-deps --user root web uv lock` → `docker compose build web` |
| Build de producción (prueba local) | `docker build --target production -t taskflow:prueba .` |
| Publicar la imagen | push a `main` → GitHub Actions (`.github/workflows/publicar-imagen.yml`) la publica en `ghcr.io/ernestoas/taskflow:<commit corto>` si pasan las pruebas (automático) |
| Desplegar en producción | en el servidor, con el usuario propio: `taskflow desplegar <commit corto>` (`docker/desplegar.sh`; manual, ver `docs/operacion.md`). Si un cambio exige pasos al desplegar, anotarlos en «Pasos propios de cada versión» de `docs/operacion.md` |

Puertos por defecto (configurables en `.env`): web `8030`, Postgres `127.0.0.1:5452`.

Problemas comunes:

- `ModuleNotFoundError` en `web` tras cambiar `pyproject.toml`: las dependencias viven en la
  imagen → `docker compose build web` y `docker compose up -d`.
- `vue-tsc: not found`: `docker compose run` no instala dependencias; usar `sh -c "npm ci && …"`.
- La PWA no refleja cambios: recompilar y recargar; si sigue igual es el service worker (cerrar la
  app instalada o DevTools → Application → Service Workers → Unregister).

## Definition of done de cada cambio

0. `docs/propuesta-arquitectura.md` actualizado en el **mismo** cambio (ver §Sincronía con la
   propuesta de arquitectura en `CLAUDE.md`).
1. `pytest` en verde.
2. `ruff check .` y `ruff format --check .` sin errores.
3. `makemigrations --check` sin cambios pendientes.
4. Si cambió Docker o settings de producción: build `--target production` y healthcheck `healthy`.
5. Ninguna URL escrita a mano: todo con `{% url %}`/`reverse()`/`{% static %}`, y en la PWA con
   `api()` de `frontend/src/api.ts` (producción vive bajo `/taskflow/`, ver `CLAUDE.md`).
6. Si cambió `frontend/`: `npm run build` sin errores (incluye `vue-tsc`) y la pantalla probada en
   teléfono (390 px) y computadora (≥ 900 px).
7. Endpoint nuevo: prueba en `apps/api/tests/` de que un no miembro recibe 404 y uno sin permiso 403.

## Estructura

- `config/settings/{base,dev,test,production}.py` — toda configuración variable viene del entorno (`django-environ`).
- `apps/<app>/` con `AppConfig.name = "apps.<app>"` y `label = "<app>"`.
- Plantillas globales en `templates/`; plantillas de app en `apps/<app>/templates/<app>/`.
- Diseño: `docs/propuesta-arquitectura.md`. **No implementar modelos de dominio que no estén
  en ese documento; si el diseño cambia, actualízalo primero.**

## Convenciones

- Modelos, campos, URLs y textos de UI **en español** (identificadores sin acentos, `verbose_name` con acentos).
  Los nombres heredados de Django se quedan en inglés.
- Nuevas apps: `mkdir apps/<nombre>` y `docker compose exec web python manage.py startapp <nombre> apps/<nombre>`;
  ajustar `name`/`label` en `apps.py` y registrar en `LOCAL_APPS`.
- Modelos con fechas de auditoría heredan de `apps.core.models.TimeStampedModel`.
- Opciones fijas con `models.TextChoices` dentro del modelo (p. ej. `Tarjeta.Estatus`), reforzadas
  con `CheckConstraint` cuando sea un valor crítico.
- Pruebas con `pytest` en `apps/<app>/tests/test_*.py`; fixtures compartidas en `conftest.py`.
- Commits en español.

## Dónde está cada cosa

- `apps/core`: `TimeStampedModel`, `/healthz/` y su middleware (responde antes de `ALLOWED_HOSTS`).
- `apps/usuarios`: `Usuario` (`AUTH_USER_MODEL`), el correo es la credencial; sin `username`.
- `apps/proyectos`: `Proyecto`, `MiembroProyecto` (rol y cinco permisos), `Invitacion`,
  `TipoTarjeta`; `servicios.py` con todas las reglas (permisos, invitar, transferir, archivar…).
- `apps/tarjetas`: `Tarjeta` (proyecto, título, descripción, estatus, `fecha_fin`, `asignados`,
  `tipos`, `creada_por`) y `CambioEstatus` (historial); `servicios.py` con crear, editar,
  `cambiar_estatus` (única vía para cambiar el estatus) y eliminar.
- `apps/api`: `/api/v1/` de la PWA (`urls.py`, `vistas.py` con vistas de función de DRF que solo
  llaman servicios, `representacion.py` con la salida JSON, `excepciones.py` con el formato de
  errores).
- `apps/core/views.py`: portada (`core/portada.html`) y `pwa` (entrega `pwa/app/index.html` o 503
  si no está compilada; normalmente la sirve WhiteNoise con `WHITENOISE_ROOT`).
- `frontend/src/`: `api.ts` (cliente y raíz), `sesion.ts`, `ui.ts` (avisos y confirmaciones),
  `instalacion.ts`, `router.ts` (rutas con `#`), `vistas/` (pantallas), `componentes/`,
  `estilos.css` (componentes; colores de `static/css/tema.css`).
- Pruebas: fixtures `crear_usuario`, `dueno`, `proyecto` y `agregar_miembro` en `conftest.py`.

## Documentación

Para APIs de Django usa la skill `django-docs`.
