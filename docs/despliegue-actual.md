# TaskFlow — Cómo está montado hoy y qué cambiar al migrar

> **Fecha:** 2026-10-01 · **Versión activa:** `f6d2e40` (primera: `2df6d82`).
> Este documento es el **inventario** del despliegue: qué hay en el servidor, qué se configuró
> *solo porque TaskFlow comparte servidor y dominio*, y la lista exacta de cambios para
> (A) darle dominio propio o (B) moverlo a un servidor donde esté solo.
> Procedimientos generales (desplegar, respaldar, volver atrás): [operacion.md](operacion.md).
> **Mantenerlo al día** cada vez que se toque el servidor o una de estas configuraciones.

---

## 1. Situación actual

| Dato | Valor |
| --- | --- |
| URL pública | **https://sistemas.reduaz.mx/taskflow/** (admin: `/taskflow/django-admin/`) |
| Servidor | Debian 13 · `sistemas.reduaz.mx` · 148.217.94.155 · 8 GB de RAM |
| SSH | puerto **4022** (`ssh -p 4022 <usuario>@148.217.94.155`) |
| Usuario que lo instaló | `leaguilar` (grupos `docker`, `mi-campus-admin`, `taskflow-admin`; `sudo` por regla de sudoers, no por el grupo `sudo`) |
| Repositorio | `github.com/ErnestoAS/TaskFlow` (**privado**) |
| Imagen | `ghcr.io/ernestoas/taskflow:<commit corto>` (privada; la publica GitHub Actions) |
| Directorio | `/opt/taskflow` (`compose.prod.yaml`, `.env`, `.env.prod`) |
| Proyecto de Compose | `taskflow-prod` (contenedores `taskflow-prod-db-1` y `taskflow-prod-web-1`) |
| Volúmenes | `taskflow-prod_db-data`, `taskflow-prod_media` |
| Puerto | `web` publicado solo en **`127.0.0.1:8082`**; PostgreSQL **sin publicar** |
| Certificado | El de actividades-uaz: `/etc/letsencrypt/live/sistemas.reduaz.mx/` (cubre `sistemas.reduaz.mx` y `cv.reduaz.mx`) |
| Comando de despliegue | `/usr/local/bin/taskflow` (copia de `docker/desplegar.sh`) |
| Respaldos | `/var/backups/taskflow/` (grupo `taskflow-admin`, `2770`), con `historial.log` |

### Con quién comparte

| Aplicación | Qué ocupa en el servidor | Dónde vive |
| --- | --- | --- |
| **actividades-uaz** (`gestioneducativa`) | nginx en 80/443/8080; contenedor en `127.0.0.1:8001`; **PostgreSQL publicado en 5432**; es **dueña del archivo de nginx** y del certificado | `/opt/sistemas/gestioneducativa` · `/etc/nginx/sites-available/gestioneducativa` |
| **mi-campus** | nginx interno en `127.0.0.1:8081`; sus dominios `micampus.uaz.edu.mx`, `medicina.uaz.edu.mx` con sus propios `server{}` | `/opt/mi-campus` |
| **TaskFlow** | `127.0.0.1:8082`, ruta `/taskflow/` dentro del sitio de actividades-uaz | `/opt/taskflow` |

```
Internet ──443──► nginx del servidor (certificado de sistemas.reduaz.mx)
                    ├─ /taskflow/…  ─► (quita /taskflow) ─► 127.0.0.1:8082  TaskFlow (gunicorn + WhiteNoise)
                    └─ /…           ─► 127.0.0.1:8001                      actividades-uaz
         (micampus.uaz.edu.mx y medicina.uaz.edu.mx tienen su propio server{} ─► 127.0.0.1:8081)
```

## 2. Lo que se hizo en el servidor (inventario)

Todo lo que existe fuera de `/opt/taskflow`, para saber qué limpiar o rehacer al migrar.

| Qué | Dónde | Notas |
| --- | --- | --- |
| Carpeta de la app | `/opt/taskflow` (root, `755`) | `.env.prod` con permisos `600` |
| Grupo | `taskflow-admin` | `leaguilar` es miembro |
| Carpeta de respaldos | `/var/backups/taskflow` (root:`taskflow-admin`, `2770`) | **Copiarla fuera antes de borrar nada** |
| Script | `/usr/local/bin/taskflow` | Se reinstala cuando cambia `docker/desplegar.sh` |
| Snippet de nginx | `/etc/nginx/snippets/taskflow.conf` | Copia de `docker/nginx/taskflow.conf` |
| **Línea agregada al sitio de actividades-uaz** | `/etc/nginx/sites-available/gestioneducativa`, dentro del `server` de 443, antes de `location / {` | `include /etc/nginx/snippets/taskflow.conf;` con un comentario arriba |
| Copia previa del sitio | `~leaguilar/gestioneducativa.antes-de-taskflow` | Estado del archivo antes del `include` |
| Archivos sueltos | `~leaguilar/{compose.prod.yaml,.env.prod.example,desplegar.sh,taskflow.conf}` | Ya se instalaron; se pueden borrar |
| Login de ghcr.io | `~leaguilar/.docker/config.json` | Ya descargaba la imagen privada sin hacer login nuevo |

Incidencias de la primera instalación (2026-10-01):

- `DATABASE_URL` quedó con una contraseña distinta de `POSTGRES_PASSWORD` (7 caracteres de más) y
  `web` no conectaba. Se corrigió reescribiendo `DATABASE_URL` desde `POSTGRES_PASSWORD`
  (`operacion.md`). PostgreSQL fija la contraseña **solo** al crear el volumen: cambiar
  `POSTGRES_PASSWORD` después no cambia la de la base.
- El admin salía sin estilos (versión `2df6d82`): `STATIC_URL` relativa se quedaba en caché sin el
  prefijo. Corregido en `f6d2e40` (§11 de la propuesta).

## 3. Configuraciones que existen solo por compartir

| # | Configuración | Dónde está | Por qué existe | Con dominio propio | En servidor propio |
| --- | --- | --- | --- | --- | --- |
| 1 | `DJANGO_FORCE_SCRIPT_NAME=/taskflow` | `/opt/taskflow/.env.prod` (y `.env.prod.example`) | Vive en una ruta, no en la raíz de un dominio | **Vaciar** (`DJANGO_FORCE_SCRIPT_NAME=`) | Vaciar si tiene dominio; si se sigue usando una ruta, mantener |
| 2 | `STATIC_URL`/`MEDIA_URL = RUTA_BASE + …` | `config/settings/base.py` | Prefijo explícito para que gunicorn no lo pierda | **No tocar**: sin prefijo da `/static/` solo | No tocar |
| 3 | Cookies `taskflow_sessionid` / `taskflow_csrftoken` con ruta `RUTA_BASE` | `config/settings/base.py` | No pisar las de actividades-uaz en el mismo dominio | Pueden quedarse (la ruta pasa sola a `/`). Las sesiones abiertas se pierden al cambiar | Igual |
| 4 | `healthz` compara `request.path_info` | `apps/core/middleware.py` | Con prefijo, `path` trae `/taskflow/` | No tocar (funciona con y sin prefijo) | No tocar |
| 5 | Regla «ninguna URL escrita a mano» | `CLAUDE.md`, skill `taskflow-dev` | Una ruta absoluta saldría de `/taskflow/` y caería en actividades-uaz | Conservar la regla (es buena práctica); quitar la mención a actividades-uaz | Igual |
| 6 | Puerto **8082** en loopback | `/opt/taskflow/.env` (`TASKFLOW_HTTP_PORT`), defaults en `compose.prod.yaml`, `docker/nginx/taskflow.conf`, `docker/desplegar.sh` | 8001 y 8081 ya estaban tomados | Mantener | Puede quedarse o cambiar; si cambia, cambiar en los **cuatro** lugares |
| 7 | PostgreSQL sin publicar | `compose.prod.yaml` | El 5432 es de actividades-uaz | Mantener | Mantener (no hace falta publicarlo) |
| 8 | Gunicorn con **2 workers** | `/opt/taskflow/.env.prod` (`GUNICORN_CMD_ARGS`) | La RAM se reparte entre tres apps | Mantener | Subir (regla común: `2 × núcleos + 1`) |
| 9 | `DJANGO_SECURE_HSTS_SECONDS=0` | `/opt/taskflow/.env.prod` | `sistemas.reduaz.mx` conserva el 8080 de actividades-uaz y HSTS aplica a todos los puertos del dominio | **Se puede activar** en el dominio nuevo: empezar con `300`, luego `31536000` | Igual |
| 10b | `TASKFLOW_URL=https://sistemas.reduaz.mx/taskflow` | `/opt/taskflow/.env.prod` | Base de los enlaces de los correos (invitaciones), con el prefijo | **Cambiar** a `https://taskflow.reduaz.mx` (sin `/taskflow`); las invitaciones ya enviadas con la URL vieja dejan de funcionar salvo que se mantenga la redirección del paso 6 | Igual |
| 10 | `DJANGO_ALLOWED_HOSTS=sistemas.reduaz.mx,localhost,127.0.0.1` y `DJANGO_CSRF_TRUSTED_ORIGINS=https://sistemas.reduaz.mx` | `/opt/taskflow/.env.prod` | Dominio de actividades-uaz | **Cambiar** al dominio nuevo (dejar `localhost,127.0.0.1`) | Igual |
| 11 | `include` en el sitio de actividades-uaz + snippet | `/etc/nginx/sites-available/gestioneducativa`, `/etc/nginx/snippets/taskflow.conf` | Reutilizar su `server{}` y su certificado | **Quitar** el `include`; crear un `server{}` propio | No existe en el servidor nuevo; crear `server{}` propio |
| 12 | `HOST_SALUD=sistemas.reduaz.mx` | `docker/desplegar.sh` (o variable `TASKFLOW_HOST_SALUD`) | Cabecera `Host` de la prueba de salud | Cambiar al dominio nuevo (no es crítico: `/healthz/` responde antes de validar el host) | Igual |
| 13 | IP, puerto SSH 4022 y dominio en la documentación | `docs/operacion.md`, `docs/guia-despliegue-colaborador.md`, `README.md`, `CLAUDE.md`, `.env.prod.example`, `compose.prod.yaml` (comentarios), `docs/propuesta-arquitectura.md` | Datos de este servidor | Cambiar URL | Cambiar IP, SSH, URL y quitar las tablas de «con quién comparte» |
| 15 | PWA con rutas `#` y `base: "./"`; la raíz de la API se calcula de la URL | `frontend/vite.config.ts`, `frontend/src/router.ts`, `frontend/src/api.ts` | La misma build funciona en `/app/` y en `/taskflow/app/` | **No tocar**: funciona igual en la raíz. Los usuarios deben **reinstalar** la app (la app instalada queda ligada a su URL; el service worker y el ícono son del dominio viejo) | Igual |
| 14 | `cv.reduaz.mx/taskflow/` responde 400 | Efecto del `include` (el `server{}` atiende los dos dominios) | Esperado; no afecta a nadie | Desaparece al quitar el `include` | No aplica |

Para encontrar todas las menciones en el repositorio:

```bash
grep -rn "sistemas.reduaz.mx\|148.217.94.155\|4022\|8082\|FORCE_SCRIPT_NAME\|/taskflow/" --exclude-dir=.git .
```

## 4. Checklist A: dominio propio en el mismo servidor

Ejemplo con `taskflow.reduaz.mx`. Nada de esto requiere una versión nueva de la imagen.

1. **DNS**: registro `A` de `taskflow.reduaz.mx` → 148.217.94.155. Esperar a que resuelva
   (`dig +short taskflow.reduaz.mx`). Sin esto certbot falla.
2. **Respaldo**: `taskflow respaldar`.
3. **Sitio propio de nginx** `/etc/nginx/sites-available/taskflow`:

   ```nginx
   server {
       server_name taskflow.reduaz.mx;
       client_max_body_size 10m;
       location / {
           proxy_pass http://127.0.0.1:8082;          # SIN diagonal final: ya no hay prefijo que quitar
           proxy_set_header Host $host;
           proxy_set_header X-Forwarded-For $remote_addr;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_redirect off;
       }
       listen 80;
   }
   ```

   ```bash
   sudo ln -s /etc/nginx/sites-available/taskflow /etc/nginx/sites-enabled/
   sudo nginx -t && sudo systemctl reload nginx
   sudo certbot --nginx -d taskflow.reduaz.mx      # certificado propio; certbot agrega el 443 y la redirección
   sudo certbot renew --dry-run
   ```

   Usar un certificado **propio** (no ampliar el de `sistemas.reduaz.mx`): así TaskFlow no depende
   del certificado de actividades-uaz.
4. **`.env.prod`** (`sudo nano /opt/taskflow/.env.prod`):

   ```
   DJANGO_FORCE_SCRIPT_NAME=
   DJANGO_ALLOWED_HOSTS=taskflow.reduaz.mx,localhost,127.0.0.1
   DJANGO_CSRF_TRUSTED_ORIGINS=https://taskflow.reduaz.mx
   TASKFLOW_URL=https://taskflow.reduaz.mx
   ```

   y `sudo docker compose -f compose.prod.yaml up -d --force-recreate web` en `/opt/taskflow`.
5. **Verificar** `https://taskflow.reduaz.mx/healthz/`, el login del admin y que se vea con
   estilos (Ctrl+F5).
6. **Opcional, mantener la dirección vieja un tiempo**: cambiar el snippet
   `/etc/nginx/snippets/taskflow.conf` por una redirección y dejar el `include`:

   ```nginx
   location ^~ /taskflow { return 301 https://taskflow.reduaz.mx$request_uri; }
   ```

   Ojo: `$request_uri` conserva `/taskflow/…`; para quitarlo, usar
   `rewrite ^/taskflow/?(.*)$ https://taskflow.reduaz.mx/$1 permanent;`.
   Si no se quiere conservar, **quitar** la línea `include` (y su comentario) de
   `/etc/nginx/sites-available/gestioneducativa`, `nginx -t` y recargar. Hacer antes
   `sudo cp` del archivo: es de actividades-uaz.
7. **HSTS** (opcional): `DJANGO_SECURE_HSTS_SECONDS=300`, recrear `web`, comprobar, y después subirlo.
8. **Repositorio** (en el mismo commit): `.env.prod.example`, `docker/desplegar.sh`
   (`HOST_SALUD`), `docker/nginx/taskflow.conf` (reemplazarlo por el `server{}` del paso 3),
   la documentación de la tabla del §3 y una nota fechada en §11 de la propuesta.
9. Avisar a los usuarios: las sesiones abiertas se cierran (cambian dominio y ruta de la cookie).

## 5. Checklist B: mover TaskFlow a un servidor donde esté solo

1. **Preparar el servidor nuevo**: Docker + Compose v2, nginx y certbot; usuarios SSH; grupos
   `docker` y `taskflow-admin`; `/var/backups/taskflow` (`2770`); `/opt/taskflow`. Pasos en
   `operacion.md`, «Primera instalación» y «Preparación para varias personas».
2. **Dominio**: si el nuevo servidor tendrá dominio propio, seguir el Checklist A en el servidor
   nuevo (DNS apuntando a la IP **nueva**). Si seguirá bajo una ruta de otro dominio, conservar
   `DJANGO_FORCE_SCRIPT_NAME` y el snippet.
3. **Copiar configuración**: `/opt/taskflow/.env.prod` tal cual (contiene la `DJANGO_SECRET_KEY`
   y la contraseña de PostgreSQL; sin ellas el respaldo de la base no sirve). Ajustar en él las
   filas 1, 8, 9 y 10 del §3. Crear `.env` con `TASKFLOW_IMAGE` (la versión activa) y
   `TASKFLOW_HTTP_PORT`.
4. **Ventana de mantenimiento** en el servidor viejo: `taskflow respaldar` y detener `web`
   (`sudo docker compose -f compose.prod.yaml stop web`) para que nadie capture datos después del
   respaldo.
5. **Llevar los datos**: copiar el `.dump` y el `media_*.tar.gz` de `/var/backups/taskflow/`
   al servidor nuevo (`scp`). En el nuevo:

   ```bash
   cd /opt/taskflow
   docker pull ghcr.io/ernestoas/taskflow:<versión activa>
   sudo docker compose -f compose.prod.yaml up -d db
   sudo docker compose -f compose.prod.yaml exec -T db pg_restore -U taskflow -d taskflow --clean --if-exists < taskflow_<...>.dump
   docker run --rm -v taskflow-prod_media:/m -v "$PWD":/r alpine tar xzf /r/media_<...>.tar.gz -C /
   sudo docker compose -f compose.prod.yaml up -d
   ```

6. **Verificar** como en «Primera instalación», paso 7 (sin las líneas de actividades-uaz).
7. **Limpiar el servidor viejo** (solo cuando el nuevo esté confirmado y los respaldos copiados
   fuera): quitar el `include` del sitio de actividades-uaz (`nginx -t`, recargar),
   `/etc/nginx/snippets/taskflow.conf`, `sudo docker compose -f compose.prod.yaml down` **sin `-v`**
   (los volúmenes se borran aparte y a mano, cuando se confirme que no hacen falta), las imágenes
   `ghcr.io/ernestoas/taskflow:*`, `/usr/local/bin/taskflow`, `/opt/taskflow` y el grupo
   `taskflow-admin`. **Nunca** `prune`: el servidor sigue teniendo actividades-uaz y mi-campus.
8. **Repositorio**: actualizar este documento, `operacion.md`, la guía de colaboradores
   (IP, SSH, URL), y quitar las restricciones de §3 que ya no apliquen; nota fechada en §11 de la
   propuesta.
