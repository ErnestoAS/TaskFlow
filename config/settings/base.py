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
    "apps.pizarras",
    "apps.tarjetas",
    "apps.api",
]

THIRD_PARTY_APPS = ["rest_framework"]

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


# Publicación bajo una ruta (docs/operacion.md). Producción vive en la raíz de su dominio
# (https://taskflow.rourendev.com/) y lo deja vacío, igual que en local. Si algún día se publica
# bajo una ruta de otro dominio (como /taskflow/ hasta 2026-10-03), el nginx de ese servidor quita
# el prefijo antes de reenviar y Django lo vuelve a anteponer en todas las URLs que genera.
FORCE_SCRIPT_NAME = env("DJANGO_FORCE_SCRIPT_NAME", default=None) or None
RUTA_BASE = (FORCE_SCRIPT_NAME or "").rstrip("/") + "/"

# Cookies con nombre y ruta propios: en local, otras aplicaciones (como mi-campus) usan
# `sessionid` y `csrftoken` en `localhost`, y bajo una ruta de un dominio compartido pasaría lo
# mismo. Con el mismo nombre una aplicación pisaría la sesión de la otra.
SESSION_COOKIE_NAME = "taskflow_sessionid"
CSRF_COOKIE_NAME = "taskflow_csrftoken"
SESSION_COOKIE_PATH = RUTA_BASE
CSRF_COOKIE_PATH = RUTA_BASE


# Archivos estáticos y media
# Con el prefijo explícito (/taskflow/static/). No usar rutas relativas ("static/"): Django les
# antepone el prefijo solo si ya está fijado la primera vez que se lee STATIC_URL, y con gunicorn
# esa primera lectura ocurre al cargar WhiteNoise, antes de cualquier petición; el valor queda en
# caché sin prefijo y el admin pide sus estilos a /static/, fuera de /taskflow/ (2026-10-01).
# WhiteNoise le quita FORCE_SCRIPT_NAME por su cuenta para comparar con la ruta ya sin prefijo.

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = env.path("DJANGO_STATIC_ROOT", default=BASE_DIR / "staticfiles")
STATIC_URL = RUTA_BASE + "static/"

MEDIA_ROOT = env.path("DJANGO_MEDIA_ROOT", default=BASE_DIR / "media")
MEDIA_URL = RUTA_BASE + "media/"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


# Correo saliente. Producción: SMTP con las variables DJANGO_EMAIL_*; sin ellas, los correos se
# imprimen en la consola (docker compose logs -f web).

EMAIL_HOST = env("DJANGO_EMAIL_HOST", default="")
EMAIL_PORT = env.int("DJANGO_EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("DJANGO_EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("DJANGO_EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("DJANGO_EMAIL_USE_TLS", default=True)
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend",
)
DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="TaskFlow <no-responder@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# API (Django REST Framework) de la PWA: misma sesión y CSRF que Django, sin tokens (§6).
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework.authentication.SessionAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "apps.api.excepciones.manejar_excepcion",
    "DEFAULT_THROTTLE_RATES": {"acceso": env("TASKFLOW_LIMITE_ACCESO", default="20/min")},
    "UNAUTHENTICATED_USER": "django.contrib.auth.models.AnonymousUser",
}

# Cualquiera puede crear su cuenta desde la app (decidido 2026-10-01, §7). Con False, solo se
# entra por invitación o con una cuenta creada en el admin.
TASKFLOW_REGISTRO_ABIERTO = env.bool("TASKFLOW_REGISTRO_ABIERTO", default=True)

# PWA (§5): el build de frontend/ queda en pwa/app/ y WhiteNoise lo sirve en /app/.
PWA_DIR = Path(env("TASKFLOW_PWA_DIR", default=str(BASE_DIR / "pwa")))
WHITENOISE_ROOT = PWA_DIR
WHITENOISE_INDEX_FILE = True
WHITENOISE_MIMETYPES = {".webmanifest": "application/manifest+json"}

# URL pública de TaskFlow, con su prefijo: se usa en los enlaces de los correos (invitaciones).
TASKFLOW_URL = env("TASKFLOW_URL", default="http://localhost:8030")


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
