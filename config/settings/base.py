"""
Settings comunes de TaskFlow.

Toda configuración que dependa del entorno se lee de variables de entorno
(ver `.env.example`). `dev.py`, `test.py` y `production.py` extienden este módulo.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("DJANGO_SECRET_KEY", default="")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])


# Aplicaciones

LOCAL_APPS = [
    "apps.core",
    "apps.usuarios",
    "apps.tarjetas",
]

THIRD_PARTY_APPS: list[str] = []

DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

INSTALLED_APPS = LOCAL_APPS + THIRD_PARTY_APPS + DJANGO_APPS

MIDDLEWARE = [
    "apps.core.middleware.HealthCheckMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# Base de datos (PostgreSQL). Formato: postgres://usuario:password@host:5432/base

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://taskflow:taskflow@db:5432/taskflow"),
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DATABASE_CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Usuarios. El modelo personalizado se define desde el inicio porque cambiarlo
# después de la primera migración es muy costoso.

AUTH_USER_MODEL = "usuarios.Usuario"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# Internacionalización

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True
LANGUAGES = [("es-mx", "Español (México)")]


# Publicación bajo una ruta (docs/operacion.md). En producción TaskFlow vive en
# https://sistemas.reduaz.mx/taskflow/: el nginx del servidor quita el prefijo antes de reenviar y
# Django lo vuelve a anteponer en todas las URLs que genera. En local queda vacío (raíz).
FORCE_SCRIPT_NAME = env("DJANGO_FORCE_SCRIPT_NAME", default=None) or None
RUTA_BASE = (FORCE_SCRIPT_NAME or "").rstrip("/") + "/"

# Cookies con nombre y ruta propios: el dominio lo comparten otras aplicaciones (actividades-uaz
# usa `sessionid` y `csrftoken` en `/`) y, en local, mi-campus en `localhost`. Con el mismo nombre
# una aplicación pisaría la sesión de la otra.
SESSION_COOKIE_NAME = "taskflow_sessionid"
CSRF_COOKIE_NAME = "taskflow_csrftoken"
SESSION_COOKIE_PATH = RUTA_BASE
CSRF_COOKIE_PATH = RUTA_BASE


# Archivos estáticos y media
# Rutas relativas a propósito: Django les antepone FORCE_SCRIPT_NAME (/taskflow/static/).

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env.path("DJANGO_STATIC_ROOT", default=BASE_DIR / "staticfiles")
STATIC_URL = "static/"

MEDIA_ROOT = env.path("DJANGO_MEDIA_ROOT", default=BASE_DIR / "media")
MEDIA_URL = "media/"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


# Logging a stdout (Docker)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": env("DJANGO_LOG_LEVEL", default="INFO")},
}
