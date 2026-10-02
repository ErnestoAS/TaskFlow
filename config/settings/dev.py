from .base import *

DEBUG = True

SECRET_KEY = env("DJANGO_SECRET_KEY", default="django-insecure-solo-para-desarrollo")

ALLOWED_HOSTS = ["*"]

# WhiteNoise sirve desde los finders sin necesidad de collectstatic.
WHITENOISE_USE_FINDERS = True
WHITENOISE_AUTOREFRESH = True

if env.bool("DJANGO_DEBUG_TOOLBAR", default=True):
    INSTALLED_APPS += ["debug_toolbar"]
    MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")
    # Dentro de Docker la IP del cliente no es 127.0.0.1.
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": lambda request: DEBUG}
