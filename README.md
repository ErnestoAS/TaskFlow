# TaskFlow

Gestor de tarjetas para organizar actividades. Cada tarjeta tiene título, descripción, fecha de
fin opcional, uno o más asignados y uno de tres estatus: **Pendiente**, **En curso** o
**Finalizada**.

## Stack

Python 3.13 · Django 5.2 LTS · Django REST Framework · PostgreSQL 18 · uv · Docker ·
PWA con Vue 3 + Vite + TypeScript

## Estructura

```
config/              settings (base, dev, test, production), urls, wsgi/asgi
apps/core/           TimeStampedModel, /healthz/, portada de instalación (/) y entrega de la PWA (/app/)
apps/usuarios/       cuenta de acceso (Usuario) con el correo como credencial
apps/proyectos/      Proyecto, MiembroProyecto (permisos), Invitacion, TipoTarjeta + servicios.py
apps/tarjetas/       Tarjeta y CambioEstatus (historial) + servicios.py
apps/api/            API de la PWA (/api/v1/)
frontend/            PWA (Vue + Vite); se compila a pwa/app/ (no se versiona)
docker/              entrypoint, script de despliegue (desplegar.sh) y snippet de nginx
.github/workflows/   pruebas y publicación de la imagen en ghcr.io
docs/                propuesta de arquitectura, identidad visual y maquetas
static/              tema.css (paleta navy + petróleo), fuentes (Inter), portada e img/marca/ (logo)
.claude/skills/      skills para asistentes de IA (flujo del proyecto, docs de Django)
```

Diseño y esquema: [docs/propuesta-arquitectura.md](docs/propuesta-arquitectura.md).

## Desarrollo

Requisitos: Docker Desktop o Docker Engine con Compose v2.

```bash
cp .env.example .env                                     # opcional: puertos
docker compose up -d                                     # construye, espera a Postgres y migra
docker compose run --rm frontend sh -c "npm ci && npm run build"   # compila la PWA (la primera vez y tras cambiar frontend/)
docker compose exec web python manage.py createsuperuser
```

| URL | Descripción |
| --- | --- |
| http://localhost:8030/ | Portada de instalación |
| http://localhost:8030/app/ | La app (PWA). Crea tu cuenta en «Crear cuenta». |
| http://localhost:5173/app/ | La app con recarga en caliente: `docker compose --profile frontend up` |
| http://localhost:8030/django-admin/ | Admin de Django (usuarios y tarjetas) |
| http://localhost:8030/healthz/ | Healthcheck |

## Comandos frecuentes

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web pytest
docker compose exec web ruff check .
docker compose exec web ruff format .
docker compose run --rm frontend sh -c "npm ci && npm run typecheck"
```

## Producción

Publicado en **https://sistemas.reduaz.mx/taskflow/** (servidor compartido con actividades-uaz y
mi-campus). Cada push a `main` corre ruff, la verificación de migraciones y las pruebas en GitHub
Actions y, si pasan, publica la imagen `ghcr.io/ernestoas/taskflow:<commit corto>`. En el servidor
se activa con `taskflow desplegar <commit corto>`.

- Primera instalación, despliegue, respaldos y vuelta atrás: [docs/operacion.md](docs/operacion.md).
- Cómo está montado hoy y qué cambiar al migrar: [docs/despliegue-actual.md](docs/despliegue-actual.md).
- Guía para quien se suma a desplegar: [docs/guia-despliegue-colaborador.md](docs/guia-despliegue-colaborador.md).

Al agregar o cambiar dependencias en `pyproject.toml`, regenerar el lock con `uv lock` y
reconstruir la imagen (`docker compose build web`).
