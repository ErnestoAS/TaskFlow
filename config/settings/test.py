from .base import *

DEBUG = False

SECRET_KEY = "django-insecure-solo-para-pruebas"

ALLOWED_HOSTS = ["*"]

WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "media-test"
TASKFLOW_ADJUNTOS_ROOT = MEDIA_ROOT / "adjuntos"

LOGGING["root"]["level"] = "WARNING"
TASKFLOW_URL = "https://ejemplo.mx/taskflow"

# Las pruebas no dependen de que la PWA esté compilada en pwa/ (WhiteNoise la serviría antes que
# la vista y cambiaría el resultado según la máquina).
PWA_DIR = BASE_DIR / "pwa-sin-compilar"
WHITENOISE_ROOT = None
