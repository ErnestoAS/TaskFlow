from .base import *

DEBUG = False

SECRET_KEY = "django-insecure-solo-para-pruebas"

ALLOWED_HOSTS = ["*"]

WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

MEDIA_ROOT = BASE_DIR / "media-test"

LOGGING["root"]["level"] = "WARNING"
