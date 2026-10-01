---
name: taskflow-dev
description: Flujo de desarrollo de TaskFlow en Docker (levantar stack, migraciones, pruebas, lint, crear apps, agregar dependencias, build de producción) y definición de terminado. Úsala antes de ejecutar comandos de Django, agregar modelos, vistas o endpoints, o cambiar la configuración de Docker.
---

# Desarrollo de TaskFlow

Todo se ejecuta **dentro de Docker**; no hay entorno virtual local. Dependencias con **uv**.

## Comandos

| Tarea | Comando |
| --- | --- |
| Levantar (migra al iniciar) | `docker compose up -d` → http://localhost:8030 (admin: `/django-admin/`) |
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

## Definition of done de cada cambio

0. `docs/propuesta-arquitectura.md` actualizado en el **mismo** cambio (ver §Sincronía con la
   propuesta de arquitectura en `CLAUDE.md`).
1. `pytest` en verde.
2. `ruff check .` y `ruff format --check .` sin errores.
3. `makemigrations --check` sin cambios pendientes.
4. Si cambió Docker o settings de producción: build `--target production` y healthcheck `healthy`.
5. Ninguna URL escrita a mano: todo con `{% url %}`/`reverse()`/`{% static %}` (producción vive
   bajo `/taskflow/`, ver `CLAUDE.md`).

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
- `apps/tarjetas`: `Tarjeta` (título, descripción, estatus, `fecha_fin` opcional, `asignados` M2M,
  `creada_por`).

## Documentación

Para APIs de Django usa la skill `django-docs`.
