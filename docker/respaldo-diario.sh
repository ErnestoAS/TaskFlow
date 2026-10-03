#!/usr/bin/env bash
# Respaldo diario automático de TaskFlow: base (pg_dump) y archivos subidos (volumen media).
#
# Lo ejecuta systemd como root (docker/systemd/taskflow-respaldo.timer), no una persona: por eso
# no usa el comando `taskflow`, que se niega a correr como root. Se instala una vez
# (docs/operacion.md, «Respaldo automático diario»):
#   sudo install -m 750 respaldo-diario.sh /usr/local/sbin/taskflow-respaldo-diario
#
# Deja los archivos en $RESPALDOS/diarios (grupo taskflow-admin) y borra los de más de $DIAS días.
# Los respaldos que hace `taskflow desplegar` quedan aparte, en $RESPALDOS, y no se borran solos.

set -Eeuo pipefail
umask 027 # Legibles por el grupo y por nadie más (contienen datos personales).

DIR="${TASKFLOW_DIR:-/opt/taskflow}"
RESPALDOS="${TASKFLOW_RESPALDOS:-/var/backups/taskflow}"
DIAS="${TASKFLOW_DIAS_RESPALDO:-14}"
PROYECTO="taskflow-prod"
DESTINO="$RESPALDOS/diarios"
FECHA="$(date +%F_%H%M)"

registrar() { printf '%s\t%s\n' "$(date -Is)" "$*" >> "$DESTINO/registro.log"; }

# La carpeta de respaldos es 2770 (setgid): lo que se cree aquí queda del grupo taskflow-admin.
install -d -m 2770 -g "$(stat -c %G "$RESPALDOS")" "$DESTINO"
trap 'registrar "FALLÓ (línea $LINENO)"; rm -f "$DESTINO"/*.parcial' ERR

# Base: se escribe a .parcial y se renombra al terminar, para no dejar un .dump cortado.
docker compose -f "$DIR/compose.prod.yaml" --project-directory "$DIR" exec -T db \
    sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$DESTINO/taskflow_$FECHA.dump.parcial"
mv "$DESTINO/taskflow_$FECHA.dump.parcial" "$DESTINO/taskflow_$FECHA.dump"

# Archivos subidos, con la misma estructura que `taskflow respaldar` (se restauran igual).
docker run --rm -v "${PROYECTO}_media:/m:ro" alpine tar czf - -C / m \
    > "$DESTINO/media_$FECHA.tar.gz.parcial"
mv "$DESTINO/media_$FECHA.tar.gz.parcial" "$DESTINO/media_$FECHA.tar.gz"

find "$DESTINO" -maxdepth 1 \( -name 'taskflow_*.dump' -o -name 'media_*.tar.gz' \) \
    -mtime +"$DIAS" -delete

registrar "ok $(du -h "$DESTINO/taskflow_$FECHA.dump" | cut -f1) base, $(du -h "$DESTINO/media_$FECHA.tar.gz" | cut -f1) archivos"
