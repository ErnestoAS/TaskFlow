#!/bin/sh
set -e

# Espera a que PostgreSQL acepte conexiones.
python - <<'PY'
import os, sys, time

import django
from django.db import connections
from django.db.utils import OperationalError

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.production")
django.setup()

for intento in range(30):
    try:
        connections["default"].ensure_connection()
        break
    except OperationalError:
        print("Esperando a la base de datos...", flush=True)
        time.sleep(2)
else:
    sys.exit("La base de datos no respondió a tiempo.")
PY

if [ "${DJANGO_MIGRATE:-0}" = "1" ]; then
    python manage.py migrate --noinput
fi

exec "$@"
