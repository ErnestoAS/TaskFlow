# syntax=docker/dockerfile:1

ARG PYTHON_VERSION=3.13
ARG UV_VERSION=0.12.15

FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv

# ---------------------------------------------------------------------------
# base: Python + uv, usuario sin privilegios
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

COPY --from=uv /uv /usr/local/bin/uv

# Ghostscript: comprime los PDF adjuntos (Etapa 3.8, §4.4).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home app \
    && mkdir -p /app /app/media /app/staticfiles \
    && chown -R app:app /app

WORKDIR /app

# ---------------------------------------------------------------------------
# dev: dependencias de desarrollo; el código se monta como volumen
# ---------------------------------------------------------------------------
FROM base AS dev

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project

COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

ENV DJANGO_SETTINGS_MODULE=config.settings.dev

USER app
EXPOSE 8000
ENTRYPOINT ["entrypoint.sh"]
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ---------------------------------------------------------------------------
# pwa: compila frontend/ (Vue + Vite) a /src/pwa/app; Django la sirve en /app/ (§5)
# ---------------------------------------------------------------------------
FROM node:24-alpine AS pwa

WORKDIR /src/frontend
RUN --mount=type=cache,target=/root/.npm \
    --mount=type=bind,source=frontend/package.json,target=package.json \
    --mount=type=bind,source=frontend/package-lock.json,target=package-lock.json \
    npm ci
COPY frontend/ ./
# La PWA importa la paleta y la tipografía de static/ (una sola fuente de colores).
COPY static/css /src/static/css
COPY static/fonts /src/static/fonts
RUN npm run build

# ---------------------------------------------------------------------------
# builder: dependencias de producción + collectstatic
# ---------------------------------------------------------------------------
FROM base AS builder

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

COPY . /app
COPY --from=pwa /src/pwa /app/pwa

RUN DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_SECRET_KEY=solo-para-collectstatic \
    DATABASE_URL=sqlite:////tmp/build.sqlite3 \
    python manage.py collectstatic --noinput

# ---------------------------------------------------------------------------
# production: imagen final
# ---------------------------------------------------------------------------
FROM python:${PYTHON_VERSION}-slim-trixie AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    DJANGO_STATIC_ROOT=/app/staticfiles \
    DJANGO_MEDIA_ROOT=/app/media \
    GUNICORN_CMD_ARGS="--bind=0.0.0.0:8000 --workers=3 --timeout=90 --access-logfile=-"

# Ghostscript: comprime los PDF adjuntos (Etapa 3.8, §4.4).
RUN apt-get update \
    && apt-get install -y --no-install-recommends ghostscript \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 1000 app \
    && useradd --system --uid 1000 --gid app --create-home app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder --chown=app:app /app /app
COPY --chmod=755 docker/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN mkdir -p /app/media && chown app:app /app/media

USER app
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/', timeout=4).status == 200 else 1)"

ENTRYPOINT ["entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application"]
