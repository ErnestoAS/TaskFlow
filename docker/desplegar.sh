#!/usr/bin/env bash
# Descarga, respaldo, despliegue y vuelta atrás de taskflow en el servidor de producción.
#
# Se instala una vez en el servidor (docs/operacion.md, «Script de despliegue»):
#   sudo install -m 755 desplegar.sh /usr/local/bin/taskflow
# y se ejecuta con el usuario propio (el que hizo `docker login ghcr.io`), nunca con sudo:
#   taskflow desplegar 1dcd6b4
#
# Solo toca el proyecto de Compose `taskflow-prod`: no borra imágenes, contenedores ni
# volúmenes de otras aplicaciones de la VM, y no construye imágenes.
#
# Varias personas pueden desplegar: los respaldos, el historial y el candado viven en una carpeta
# compartida por el grupo `taskflow-admin` (docs/operacion.md, «Preparación para varias personas»).

set -Eeuo pipefail

# Respaldos legibles por el grupo y por nadie más (contienen datos personales).
umask 027

DIR="${TASKFLOW_DIR:-/opt/taskflow}"
IMAGEN="${TASKFLOW_IMAGEN:-ghcr.io/ernestoas/taskflow}"
RESPALDOS="${TASKFLOW_RESPALDOS:-/var/backups/taskflow}"
HOST_SALUD="${TASKFLOW_HOST_SALUD:-sistemas.reduaz.mx}"
ESPERA="${TASKFLOW_ESPERA:-300}"            # segundos para que `web` quede sano
SUDO="${TASKFLOW_SUDO-sudo}"                # /opt/taskflow y .env.prod pertenecen a root
PROYECTO="taskflow-prod"
HISTORIAL="$RESPALDOS/historial.log"
CANDADO="$RESPALDOS/.candado"

SIMULAR=0
SIN_MEDIA=0
SI=0

# --- salida ---------------------------------------------------------------------------------

if [ -t 1 ]; then
    AZUL=$'\e[1;34m'; VERDE=$'\e[1;32m'; AMARILLO=$'\e[1;33m'; ROJO=$'\e[1;31m'; NORMAL=$'\e[0m'
else
    AZUL=""; VERDE=""; AMARILLO=""; ROJO=""; NORMAL=""
fi

paso() { printf '\n%s==> %s%s\n' "$AZUL" "$*" "$NORMAL"; }
bien() { printf '%s✓ %s%s\n' "$VERDE" "$*" "$NORMAL"; }
aviso() { printf '%s! %s%s\n' "$AMARILLO" "$*" "$NORMAL" >&2; }
error() { printf '%s✗ %s%s\n' "$ROJO" "$*" "$NORMAL" >&2; exit 1; }

# Ejecuta un comando que modifica algo; con --simular solo lo muestra.
ejecutar() {
    if [ "$SIMULAR" = 1 ]; then
        printf '  [simulación] %s\n' "$*"
    else
        "$@"
    fi
}

confirmar() {
    [ "$SI" = 1 ] && return 0
    local respuesta
    printf '%s%s [escribe SI para continuar]: %s' "$AMARILLO" "$1" "$NORMAL"
    read -r respuesta < /dev/tty || true
    [ "$respuesta" = "SI" ] || error "Cancelado: no se hizo ningún cambio más."
}

# --- utilidades -----------------------------------------------------------------------------

compose() {
    # --project-directory: Compose lee .env y resuelve rutas desde /opt/taskflow aunque el
    # script se ejecute en otra carpeta.
    $SUDO docker compose -f "$DIR/compose.prod.yaml" --project-directory "$DIR" "$@"
}

variable_env() {
    $SUDO grep -E "^$1=" "$DIR/.env" | tail -n 1 | cut -d= -f2- || true
}

imagen_actual() { variable_env TASKFLOW_IMAGE; }

# `1dcd6b4` → ghcr.io/…/taskflow:1dcd6b4; una referencia completa (con `:`) se respeta.
referencia() {
    local version="$1"
    if [[ "$version" =~ ^[a-z0-9./_-]+:[A-Za-z0-9._-]+$ ]]; then
        printf '%s' "$version"
    elif [[ "$version" =~ ^[0-9a-f]{7,40}$ ]]; then
        printf '%s:%s' "$IMAGEN" "$version"
    else
        error "Versión no válida: «$version». Usa el commit corto (p. ej. 1dcd6b4) o la imagen completa."
    fi
}

etiqueta() { local ref="$1"; printf '%s' "${ref##*:}"; }

foto_contenedores() {
    docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | sed -E 's/\t(Up|Exited).*/\t\1/' | sort
}

verificar_requisitos() {
    [ "$(id -u)" -ne 0 ] || error "Ejecútalo con tu usuario (el del login en ghcr.io), no con sudo ni como root."
    command -v docker > /dev/null || error "No se encontró docker."
    [ -f "$DIR/compose.prod.yaml" ] || error "No existe $DIR/compose.prod.yaml (ajusta TASKFLOW_DIR)."
    $SUDO test -f "$DIR/.env" || error "No existe $DIR/.env."
    docker info > /dev/null 2>&1 || error "Tu usuario no puede usar docker (¿está en el grupo docker?)."
}

verificar_respaldos() {
    [ -d "$RESPALDOS" ] || error "No existe $RESPALDOS: prepárala como indica docs/operacion.md («Preparación para varias personas»)."
    [ -w "$RESPALDOS" ] || error "No puedes escribir en $RESPALDOS: tu usuario debe estar en el grupo $(stat -c %G "$RESPALDOS") (y volver a iniciar sesión)."
}

# Un solo despliegue, respaldo o limpieza a la vez, aunque lo lancen dos personas.
tomar_candado() {
    [ "$SIMULAR" = 1 ] && return 0
    [ -e "$CANDADO" ] || { : > "$CANDADO"; chmod 660 "$CANDADO"; }
    exec 9>> "$CANDADO"
    if ! flock -n 9; then
        aviso "Otra persona está desplegando o respaldando ahora mismo; esperando a que termine..."
        flock 9
    fi
}

comprobar_espacio() {
    local ruta libre
    for ruta in "$RESPALDOS" /var/lib/docker; do
        libre=$(df -Pk "$ruta" 2> /dev/null | awk 'NR == 2 {print int($4 / 1024 / 1024)}') || continue
        [ -n "$libre" ] || continue
        if [ "$libre" -lt 2 ]; then
            aviso "Quedan ${libre} GB libres en $ruta."
            confirmar "¿Continuar con poco espacio?"
        fi
    done
}

esperar_salud() {
    local id estado inicio=$SECONDS
    id=$(compose ps -q web)
    [ -n "$id" ] || error "No hay contenedor web en ejecución."
    printf '  Esperando a que web quede sano (migraciones y arranque, hasta %ss)' "$ESPERA"
    while :; do
        estado=$($SUDO docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id" 2> /dev/null || echo desconocido)
        case "$estado" in
            healthy) printf '\n'; bien "web está sano."; return 0 ;;
            unhealthy | exited | dead) printf '\n'; return 1 ;;
        esac
        [ $((SECONDS - inicio)) -lt "$ESPERA" ] || { printf '\n'; return 1; }
        printf '.'
        sleep 5
    done
}

probar_healthz() {
    local puerto codigo
    puerto=$(variable_env TASKFLOW_HTTP_PORT)
    puerto="${puerto:-8082}"
    codigo=$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $HOST_SALUD" "http://127.0.0.1:$puerto/healthz/" || true)
    if [ "$codigo" = 200 ]; then
        bien "healthz responde 200 en el puerto $puerto."
    else
        aviso "healthz respondió «$codigo» en el puerto $puerto (Host: $HOST_SALUD)."
        return 1
    fi
}

registrar() {
    [ "$SIMULAR" = 1 ] && return 0
    [ -e "$HISTORIAL" ] || { : > "$HISTORIAL"; chmod 660 "$HISTORIAL"; }
    printf '%s\t%s\t%s\t%s → %s\t%s\n' "$(date '+%F %T')" "$(id -un)" "$1" "${2:--}" "$3" "${4:--}" >> "$HISTORIAL" \
        || aviso "No se pudo escribir en $HISTORIAL."
}

# --- acciones -------------------------------------------------------------------------------

descargar() {
    local ref="$1"
    paso "Descargando $ref"
    if docker image inspect "$ref" > /dev/null 2>&1; then
        bien "La imagen ya está en el servidor."
        return 0
    fi
    # Con el usuario propio: `root` no tiene la credencial de ghcr.io.
    ejecutar docker pull "$ref" || error "No se pudo descargar. Si dice «denied»: tu token de ghcr.io venció o es inválido, o tu cuenta de GitHub no tiene el rol Read sobre la imagen (docs/operacion.md)."
    [ "$SIMULAR" = 1 ] || bien "Imagen descargada."
}

respaldar() {
    local base version dump media n=1
    paso "Respaldando la base de datos y los archivos"
    version=$(etiqueta "$(imagen_actual)")
    # Fecha, quién respaldó y versión respaldada; nunca sobrescribe un respaldo existente.
    base="$(date +%F_%H%M%S)_$(id -un)"
    while [ -e "$RESPALDOS/taskflow_${base}_${version:-sin-version}.dump" ] \
        || [ -e "$RESPALDOS/media_${base}.tar.gz" ]; do
        n=$((n + 1))
        base="$(date +%F_%H%M%S)_$(id -un)-$n"
    done
    dump="$RESPALDOS/taskflow_${base}_${version:-sin-version}.dump"
    RESPALDO_BASE="$dump"

    if [ "$SIMULAR" = 1 ]; then
        printf '  [simulación] pg_dump → %s\n' "$dump"
    else
        # -T: sin terminal, que alteraría el volcado binario. Usuario y base salen del contenedor
        # (comillas simples a propósito: las variables se expanden dentro de `db`).
        # shellcheck disable=SC2016
        compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$dump" \
            || { rm -f "$dump"; error "Falló pg_dump; no se cambió nada."; }
        [ -s "$dump" ] || { rm -f "$dump"; error "El respaldo quedó vacío; no se cambió nada."; }
        compose exec -T db pg_restore -l < "$dump" > /dev/null \
            || error "El respaldo $dump no es legible por pg_restore; no se cambió nada."
        bien "Base: $dump ($(du -h "$dump" | cut -f1))."
    fi

    if [ "$SIN_MEDIA" = 1 ]; then
        aviso "Sin respaldo de archivos (--sin-media)."
        return 0
    fi
    media="$RESPALDOS/media_${base}.tar.gz"
    # Volúmenes en solo lectura; el contenedor temporal se borra al terminar (--rm).
    ejecutar docker run --rm \
        -v "${PROYECTO}_media:/m:ro" -v "$RESPALDOS:/r" \
        alpine tar czf "/r/media_${base}.tar.gz" -C / m \
        || error "Falló el respaldo de archivos; no se cambió nada."
    if [ "$SIMULAR" != 1 ]; then
        # El contenedor lo escribe como root: pasa a quien respaldó y al grupo de la carpeta.
        $SUDO chown "$(id -u):$(stat -c %g "$RESPALDOS")" "$media"
        $SUDO chmod 640 "$media"
        bien "Archivos: $media ($(du -h "$media" | cut -f1))."
    fi
}

activar() {
    local ref="$1"
    paso "Activando $ref"
    # shellcheck disable=SC2086  # $SUDO puede estar vacío
    ejecutar $SUDO sed -i "s|^TASKFLOW_IMAGE=.*|TASKFLOW_IMAGE=$ref|" "$DIR/.env"
    # Solo recrea lo que cambió (web); sin --remove-orphans ni down.
    ejecutar compose up -d
    [ "$SIMULAR" = 1 ] && return 0
    [ "$(imagen_actual)" = "$ref" ] || error "No se actualizó TASKFLOW_IMAGE en $DIR/.env."
    if ! esperar_salud; then
        compose logs --tail=40 web >&2 || true
        return 1
    fi
    probar_healthz
}

comparar_contenedores() {
    local antes="$1" despues otros
    despues=$(foto_contenedores)
    otros=$(diff <(grep -v "^${PROYECTO}-" <<< "$antes" || true) <(grep -v "^${PROYECTO}-" <<< "$despues" || true) || true)
    if [ -n "$otros" ]; then
        aviso "Cambiaron contenedores que no son de taskflow (probablemente por su cuenta, no por este script):"
        printf '%s\n' "$otros" >&2
    else
        bien "Los contenedores de otras aplicaciones siguen igual."
    fi
}

cmd_desplegar() {
    local ref anterior antes
    [ $# -ge 1 ] || error "Falta la versión. Ejemplo: taskflow desplegar 1dcd6b4"
    ref=$(referencia "$1")
    verificar_requisitos
    verificar_respaldos
    tomar_candado
    anterior=$(imagen_actual)
    if [ "$anterior" = "$ref" ]; then
        aviso "Esa versión ya está activa ($ref)."
        confirmar "¿Desplegarla de nuevo?"
    fi
    printf 'Versión actual: %s\nVersión nueva:  %s\n' "${anterior:-(ninguna)}" "$ref"
    antes=$(foto_contenedores)
    comprobar_espacio
    descargar "$ref"             # primero: si falla, no se respalda ni se toca nada
    respaldar
    if ! activar "$ref"; then
        registrar desplegar "$anterior" "$ref (FALLÓ)" "${RESPALDO_BASE:-}"
        aviso "La versión nueva no quedó sana. Para volver a la anterior (con la base de antes):"
        printf '  taskflow volver %s %s\n' "$(etiqueta "$anterior")" "${RESPALDO_BASE:-<respaldo.dump>}" >&2
        exit 1
    fi
    [ "$SIMULAR" = 1 ] && { bien "Simulación terminada: no se cambió nada."; return 0; }
    comparar_contenedores "$antes"
    registrar desplegar "$anterior" "$ref" "${RESPALDO_BASE:-}"
    paso "Listo"
    printf 'Activa: %s\nRespaldo previo: %s\n' "$ref" "${RESPALDO_BASE:-}"
    printf 'Si hay que volver atrás:\n  taskflow volver %s %s\n' "$(etiqueta "$anterior")" "${RESPALDO_BASE:-}"
    printf 'Revisa si la versión pide pasos propios (docs/operacion.md y §11 de la propuesta).\n'
}

cmd_volver() {
    local ref dump anterior
    [ $# -ge 1 ] || error "Falta la versión. Ejemplo: taskflow volver 3104e6d [respaldo.dump]"
    ref=$(referencia "$1")
    dump="${2:-}"
    verificar_requisitos
    verificar_respaldos
    tomar_candado
    anterior=$(imagen_actual)
    if [ -n "$dump" ]; then
        [ -s "$dump" ] || error "No existe o está vacío: $dump"
        aviso "Se restaurará la base con $dump: se PIERDE todo lo capturado después de ese respaldo."
    else
        aviso "Sin respaldo: solo se cambia la imagen. Úsalo únicamente si la versión actual no trajo migraciones."
    fi
    printf 'De: %s\nA:  %s\n' "${anterior:-(ninguna)}" "$ref"
    confirmar "¿Volver a $ref?"
    descargar "$ref"
    if [ -n "$dump" ]; then
        # Respaldo de lo actual antes de sobrescribirlo, por si hay que recuperar algo después.
        respaldar
        paso "Restaurando la base desde $dump"
        ejecutar compose stop web
        if [ "$SIMULAR" = 1 ]; then
            printf '  [simulación] pg_restore --clean --if-exists < %s\n' "$dump"
        else
            # shellcheck disable=SC2016  # se expanden dentro de `db`
            compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < "$dump" \
                || aviso "pg_restore terminó con advertencias; revisa que el sitio funcione."
        fi
    fi
    activar "$ref" || error "La versión $ref tampoco quedó sana; revisa los registros: sudo docker compose -f $DIR/compose.prod.yaml logs web"
    registrar volver "$anterior" "$ref" "$dump"
    [ "$SIMULAR" = 1 ] && { bien "Simulación terminada: no se cambió nada."; return 0; }
    bien "Activa de nuevo: $ref"
}

cmd_respaldar() {
    verificar_requisitos
    verificar_respaldos
    tomar_candado
    comprobar_espacio
    respaldar
}

cmd_descargar() {
    local ref
    [ $# -ge 1 ] || error "Falta la versión. Ejemplo: taskflow descargar 1dcd6b4"
    ref=$(referencia "$1")
    verificar_requisitos
    descargar "$ref"
}

cmd_estado() {
    verificar_requisitos
    paso "Versión activa"
    printf '%s\n' "$(imagen_actual)"
    paso "Contenedores de taskflow"
    compose ps
    paso "Versiones descargadas en el servidor"
    docker image ls "$IMAGEN" --format '{{.Tag}}\t{{.CreatedSince}}\t{{.Size}}'
    paso "Últimos respaldos ($RESPALDOS)"
    # shellcheck disable=SC2012  # nombres generados por este script, sin espacios
    ls -1t "$RESPALDOS"/*.dump "$RESPALDOS"/*.tar.gz 2> /dev/null | head -n 6 || printf '(ninguno)\n'
    paso "Últimos despliegues"
    tail -n 5 "$HISTORIAL" 2> /dev/null || printf '(sin historial)\n'
}

cmd_limpiar() {
    local actual anterior tag borrar=()
    verificar_requisitos
    verificar_respaldos
    tomar_candado
    actual=$(etiqueta "$(imagen_actual)")
    # La versión anterior (último «de» del historial compartido) se conserva para poder volver.
    anterior=$(awk -F'\t' '$3 == "desplegar" && $4 !~ /FALLÓ/ {split($4, a, " → "); print a[1]}' "$HISTORIAL" 2> /dev/null | tail -n 1)
    anterior=$(etiqueta "$anterior")
    while read -r tag; do
        [ -n "$tag" ] || continue
        case "$tag" in "$actual" | "$anterior" | latest | "<none>") continue ;; esac
        borrar+=("$IMAGEN:$tag")
    done < <(docker image ls "$IMAGEN" --format '{{.Tag}}')
    if [ ${#borrar[@]} -eq 0 ]; then
        bien "No hay versiones viejas que borrar (se conservan la activa y la anterior)."
        return 0
    fi
    printf 'Se conservan: %s y %s\nSe borrarán solo estas imágenes de taskflow:\n' "$actual" "${anterior:-(sin anterior)}"
    printf '  %s\n' "${borrar[@]}"
    confirmar "¿Borrarlas?"
    ejecutar docker image rm "${borrar[@]}"
}

ayuda() {
    cat << EOF
Uso: taskflow <acción> [argumentos] [opciones]

Acciones:
  desplegar <versión>          Descarga, respalda, activa y verifica. <versión> es el commit
                               corto que publicó GitHub Actions (p. ej. 1dcd6b4).
  volver <versión> [respaldo]  Vuelve a una versión. Con un .dump, restaura también la base
                               (necesario si la versión actual aplicó migraciones).
  respaldar                    Solo respalda la base y los archivos.
  descargar <versión>          Solo descarga la imagen, sin activarla.
  estado                       Versión activa, contenedores, versiones descargadas y respaldos.
  limpiar                      Borra versiones viejas de taskflow (conserva la activa y la
                               anterior; nunca toca imágenes de otras aplicaciones).

Opciones:
  --simular     Muestra lo que haría sin cambiar nada (la descarga y el respaldo tampoco).
  --sin-media   No respalda los archivos subidos (solo la base).
  --si          No pide confirmación.

Variables (valores actuales):
  TASKFLOW_DIR=$DIR
  TASKFLOW_IMAGEN=$IMAGEN
  TASKFLOW_RESPALDOS=$RESPALDOS   (compartida por el grupo de quienes despliegan)
  TASKFLOW_HOST_SALUD=$HOST_SALUD
EOF
}

# --- entrada --------------------------------------------------------------------------------

main() {
    local accion="${1:-ayuda}" argumentos=()
    [ $# -gt 0 ] && shift
    while [ $# -gt 0 ]; do
        case "$1" in
            --simular) SIMULAR=1 ;;
            --sin-media) SIN_MEDIA=1 ;;
            --si) SI=1 ;;
            -h | --help) ayuda; exit 0 ;;
            -*) error "Opción desconocida: $1" ;;
            *) argumentos+=("$1") ;;
        esac
        shift
    done
    [ "$SIMULAR" = 1 ] && aviso "Simulación: no se cambiará nada."
    case "$accion" in
        desplegar) cmd_desplegar "${argumentos[@]}" ;;
        volver) cmd_volver "${argumentos[@]}" ;;
        respaldar) cmd_respaldar ;;
        descargar) cmd_descargar "${argumentos[@]}" ;;
        estado) cmd_estado ;;
        limpiar) cmd_limpiar ;;
        ayuda | -h | --help) ayuda ;;
        *) ayuda; exit 1 ;;
    esac
}

main "$@"
