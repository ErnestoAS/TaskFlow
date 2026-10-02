# TaskFlow — Operación en producción

Procedimientos del servidor Docker de producción (`compose.prod.yaml`). Diseño en
[propuesta-arquitectura.md](propuesta-arquitectura.md). **Inventario de cómo está montado hoy, con
quién comparte y qué cambiar para darle dominio propio o moverlo de servidor:
[despliegue-actual.md](despliegue-actual.md).** Adaptado de `docs/operacion.md` de
mi-campus, que comparte servidor y mecanismo de despliegue.

## Reparto de responsabilidades

| Capa | Quién | Qué hace |
| --- | --- | --- |
| nginx del **servidor** (fuera de Docker) | Administración del servidor | Atiende 80/443, termina TLS con el certificado de `sistemas.reduaz.mx` y reenvía `/taskflow/` a `127.0.0.1:$TASKFLOW_HTTP_PORT` (8082). |
| `web` (gunicorn + WhiteNoise) | Este repositorio | Django. Sirve también los estáticos. |
| `db` (PostgreSQL 18) | Este repositorio | No se publica fuera de Docker. |

No hay nginx interno (a diferencia de mi-campus): TaskFlow no tiene archivos privados que entregar
con `X-Accel-Redirect`, y WhiteNoise basta para los estáticos.

## Servidor

| Dato | Valor |
| --- | --- |
| Servidor | Debian 13, `sistemas.reduaz.mx` · 148.217.94.155 |
| Acceso | SSH en el puerto **4022** (`ssh -p 4022 <usuario>@148.217.94.155`, `scp -P 4022 …`) |
| Directorio | `/opt/taskflow` (`compose.prod.yaml`, `.env`, `.env.prod`) |
| Puerto de `web` | **8082** en loopback (`TASKFLOW_HTTP_PORT`) |
| URL pública | **https://sistemas.reduaz.mx/taskflow/** (sin dominio propio, ver abajo) |
| Respaldos | `/var/backups/taskflow` (grupo `taskflow-admin`) |

La VM la comparten **tres aplicaciones**. Antes de tocar puertos o nginx:

| Aplicación | Puertos en el servidor | Dónde vive |
| --- | --- | --- |
| actividades-uaz (`gestioneducativa`) | nginx 80/443/8080 → `127.0.0.1:8001`; PostgreSQL en **5432** | `/opt/sistemas/gestioneducativa` |
| mi-campus | `127.0.0.1:8081` | `/opt/mi-campus` |
| **TaskFlow** | `127.0.0.1:8082` | `/opt/taskflow` |

Comprobar que el puerto sigue libre antes de la primera instalación:
`sudo ss -lntp | grep -E ':8082\b'` no debe mostrar nada.

La VM tiene 8 GB de RAM entre las tres: gunicorn usa 2 workers (`GUNICORN_CMD_ARGS` en
`.env.prod`) y la imagen **no se construye en el servidor**.

### Por qué `/taskflow/` y no un dominio propio

Por ahora no se pueden pedir más dominios. Entrar por la IP y un puerto (`http://148.217.94.155:8082`)
dejaría a TaskFlow **sin HTTPS** (Let's Encrypt no emite certificados para una IP como para un
dominio): las contraseñas viajarían en claro y habría que abrir el puerto en el firewall. Publicarlo
como ruta del dominio que ya existe reutiliza su certificado y no abre nada.

Cómo funciona:

- El nginx del servidor recibe `https://sistemas.reduaz.mx/taskflow/…`, **quita el prefijo** y
  reenvía a `web` (`proxy_pass http://127.0.0.1:8082/;`, con la diagonal final).
- Django tiene `DJANGO_FORCE_SCRIPT_NAME=/taskflow` y antepone el prefijo a todas las URLs que
  genera (redirecciones, admin, estáticos en `/taskflow/static/`).
- Las cookies se llaman `taskflow_sessionid` y `taskflow_csrftoken` y tienen ruta `/taskflow/`,
  para no pisar las de actividades-uaz, que usa `sessionid` y `csrftoken` en `/`.
- `SECURE_HSTS_SECONDS` se queda en **0**: el dominio conserva el 8080 para enlaces viejos de
  actividades-uaz, y HSTS aplica al dominio con todos sus puertos
  (`Despliegue-HTTPS-Nginx.md` de actividades-uaz).

**Si algún día TaskFlow tiene dominio propio:** emitir su certificado, crear su `server{}` con
`location / { proxy_pass http://127.0.0.1:8082; … }` (sin diagonal final), quitar el `include`
del snippet, y en `.env.prod` dejar `DJANGO_FORCE_SCRIPT_NAME=` vacío y poner el dominio en
`DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS`. Las sesiones abiertas se pierden (cambia la
ruta de la cookie).

### Los dos archivos de entorno

Son dos porque Compose resuelve dos cosas distintas, y **ninguna variable va en los dos**:

| Archivo | Quién lo lee | Qué contiene |
| --- | --- | --- |
| `.env.prod` | Los contenedores (`env_file:`) | Configuración de Django y PostgreSQL. Permisos `600`. |
| `.env` | Docker Compose | Solo `TASKFLOW_IMAGE` y `TASKFLOW_HTTP_PORT`, para interpolar `${...}` en `compose.prod.yaml`. |

`env_file:` no participa en la interpolación: poner `TASKFLOW_HTTP_PORT` en `.env.prod` no cambia el
puerto publicado. Si `.env` falta, Compose usa `taskflow:latest` (que no existe en el servidor) y
el arranque falla.

## Primera instalación

Una sola vez. Lo hace quien administra el servidor (necesita `sudo`).

**1. Publicar la primera imagen.** Push a `main` del repositorio `ErnestoAS/TaskFlow`; esperar a
que la corrida «Pruebas y publicación de la imagen» termine en verde (pestaña *Actions*). La
versión es el commit corto del resumen. La primera publicación crea el paquete
`ghcr.io/ernestoas/taskflow`, **privado** si el repositorio es privado.

**2. Copiar los archivos al servidor** (desde tu equipo, en la carpeta del repositorio):

```bash
scp -P 4022 compose.prod.yaml .env.prod.example docker/desplegar.sh docker/nginx/taskflow.conf <usuario>@148.217.94.155:~/
```

**3. Preparar `/opt/taskflow`** (en el servidor):

```bash
sudo install -d -m 755 /opt/taskflow
sudo install -m 644 ~/compose.prod.yaml /opt/taskflow/
sudo install -m 600 ~/.env.prod.example /opt/taskflow/.env.prod
python3 -c "import secrets; print(secrets.token_urlsafe(50))"     # → DJANGO_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(24))"     # → contraseña de PostgreSQL
sudo nano /opt/taskflow/.env.prod     # secret key, y la contraseña en POSTGRES_PASSWORD y DATABASE_URL
printf 'TASKFLOW_IMAGE=ghcr.io/ernestoas/taskflow:<versión>\nTASKFLOW_HTTP_PORT=8082\n' | sudo tee /opt/taskflow/.env
```

**4. Grupo, carpeta de respaldos y script** (ver «Preparación para varias personas»).

**5. Descargar y levantar** (con tu usuario, después de `docker login ghcr.io`, ver «Acceso a la
imagen»):

```bash
docker pull ghcr.io/ernestoas/taskflow:<versión>
cd /opt/taskflow
sudo docker compose -f compose.prod.yaml up -d
sudo docker compose -f compose.prod.yaml ps                 # web: healthy (tarda unos segundos)
curl -s http://127.0.0.1:8082/healthz/                      # {"status": "ok"}
sudo docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
```

**6. Publicarlo en nginx.** El archivo de sitio es de actividades-uaz: un error de sintaxis tumba
las tres aplicaciones, así que **siempre** `nginx -t` antes de recargar.

```bash
sudo cp /etc/nginx/sites-available/gestioneducativa ~/gestioneducativa.antes-de-taskflow
sudo install -m 644 ~/taskflow.conf /etc/nginx/snippets/taskflow.conf
sudo nano /etc/nginx/sites-available/gestioneducativa
```

Dentro del bloque `server` que tiene `listen 443 ssl`, justo antes de `location / {`, agregar
**una** línea:

```nginx
    include /etc/nginx/snippets/taskflow.conf;
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

Si `nginx -t` falla, no recargar: restaurar la copia
(`sudo cp ~/gestioneducativa.antes-de-taskflow /etc/nginx/sites-available/gestioneducativa`).
No hace falta tocar el certificado ni los bloques de 80/8080 (ya redirigen todo a HTTPS).

**7. Verificar:**

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://sistemas.reduaz.mx/taskflow      # 301 …/taskflow/
curl -s https://sistemas.reduaz.mx/taskflow/healthz/                                              # {"status": "ok"}
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://sistemas.reduaz.mx/taskflow/django-admin/   # 302 …/taskflow/django-admin/login/…
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://sistemas.reduaz.mx/              # 302 …/ge/usuarios/login/ (actividades-uaz intacta)
```

Y en el navegador: **iniciar sesión** en `https://sistemas.reduaz.mx/taskflow/django-admin/` (valida
CSRF, cookies `Secure` y el prefijo de una vez) y comprobar que el admin se ve con estilos. Después,
abrir actividades-uaz en la misma ventana y confirmar que su sesión sigue viva.

## Despliegue de una versión (GitHub Actions + ghcr.io)

Guía paso a paso para quien despliega por primera vez:
[guia-despliegue-colaborador.md](guia-despliegue-colaborador.md).

```
tu equipo                 GitHub (automático)                        servidor (una persona)
─────────                 ───────────────────                        ──────────────────────
merge/push a main  ──►    ruff + migraciones + pruebas
                          └─ si pasan: construye la imagen   ──►     taskflow desplegar <versión>
                             y la publica en ghcr.io                 (descarga, respalda, activa,
                             (etiqueta = commit corto)                verifica)
                                                                     + pasos propios de la versión
```

**El servidor nunca se actualiza solo.** Publicar una imagen no cambia producción: alguien tiene
que desplegarla, para respaldar justo antes y elegir el momento del reinicio.

| Etapa | ¿Automática? | Cómo |
| --- | --- | --- |
| Llevar los cambios a `main` | No | Una persona hace el merge y el push. |
| Ruff, verificación de migraciones y pruebas | **Sí** | GitHub Actions, en cada push a `main`. Si fallan, no se publica nada. |
| Construir la imagen y publicarla en `ghcr.io` | **Sí** | GitHub Actions, solo si pasan las pruebas. Etiquetas: commit corto y `latest`. |
| Descargar, respaldar, activar y verificar | Con un comando | `taskflow desplegar <versión>`. |
| Aplicar migraciones | **Sí** | Al arrancar `web` (`DJANGO_MIGRATE=1`). |
| Pasos propios de una versión | No | A mano; ver «Pasos propios de cada versión». |
| Volver a la versión anterior | Con un comando | `taskflow volver <versión> [respaldo]`. |
| Copiar respaldos fuera del servidor | No | A mano. |
| Actualizar `compose.prod.yaml` o `docker/nginx/taskflow.conf` en el servidor | No | A mano, solo cuando cambian. |
| Reinstalar el script `taskflow` | No | A mano, solo cuando cambia `docker/desplegar.sh`. |

Workflow: [`.github/workflows/publicar-imagen.yml`](../.github/workflows/publicar-imagen.yml).
Costo con repositorio privado en el plan Free: el límite son los **2,000 minutos al mes de
Actions** (compartidos con los demás repositorios de la cuenta); conviene juntar cambios en un
solo push.

### Qué toca y qué no

Los comandos `docker compose -f compose.prod.yaml …` actúan solo sobre el proyecto
`taskflow-prod` (fijado con `name:`). **Nunca** usar en esta VM:

| Comando | Riesgo |
| --- | --- |
| `docker system prune`, `docker image prune -a` | Borra imágenes y contenedores detenidos de **todas** las aplicaciones. |
| `docker volume prune` | Puede borrar volúmenes de datos de otras aplicaciones. |
| `docker compose … down -v` | Borra los volúmenes de TaskFlow, incluida la base de datos. |
| `docker compose … up --remove-orphans` | Elimina contenedores del proyecto que ya no estén en el archivo. |

### Permisos en el servidor

`/opt/taskflow` pertenece a `root`: `sed -i` y `docker compose` (que lee `.env.prod`, permisos
`600`) necesitan `sudo`. El `docker pull` se hace **con el usuario propio** (el que tiene el login
de ghcr.io) y **antes** de `sudo docker compose up`: `root` no tiene esa credencial, y como `web`
tiene sección `build`, si la imagen no está descargada Compose intentaría construirla en la VM.

### Acceso a la imagen: una cuenta de GitHub y un token por persona

La imagen es privada. Cada persona que despliega descarga con **su propia cuenta de GitHub** y
**su propio token**.

**1. La cuenta dueña (`ErnestoAS`) da permiso de lectura** (una vez por persona): perfil →
*Packages* → `taskflow` → *Package settings* → *Manage access* → *Invite teams or people* →
usuario de GitHub de la persona → rol **Read**. No da acceso al código.

- Si indica que el acceso se hereda del repositorio, desmarcar *Inherit access from repository*
  para poder invitar, y en *Manage Actions access* confirmar que `ErnestoAS/TaskFlow` sigue con
  rol **Write** (con él publica el workflow).

**2. Cada persona crea su token** *classic* con solo **`read:packages`** y fecha de vencimiento
(*Settings → Developer settings → Personal access tokens → Tokens (classic)*). Los tokens
*fine-grained* (`github_pat_…`) **no** sirven para el registro de contenedores.

**3. Cada persona inicia sesión en el servidor**, con su usuario:

```bash
read -rs GHCR_TOKEN       # pegar el token y Enter; no se muestra
echo "$GHCR_TOKEN" | docker login ghcr.io -u <su-usuario-de-GitHub> --password-stdin
unset GHCR_TOKEN
```

Si alguien ya hizo `docker login ghcr.io` para mi-campus, **es la misma credencial**: solo
necesita además el rol Read sobre el paquete `taskflow`.

| Síntoma | Causa | Solución |
| --- | --- | --- |
| Token empieza con `github_pat_` | Token fine-grained | Crear uno *classic* |
| `docker login` responde `denied` / 401 | Token vencido, revocado o mal copiado | Crear uno nuevo |
| `docker login` funciona, `docker pull` responde `denied` | La cuenta no tiene acceso al paquete | Paso 1 |

### Preparación para varias personas (una sola vez)

**A. Quien administra el servidor** (con `sudo`):

```bash
sudo groupadd taskflow-admin
sudo usermod -aG taskflow-admin,docker <usuario>
sudo install -d -m 2770 -o root -g taskflow-admin /var/backups/taskflow
sudo install -m 755 ~/desplegar.sh /usr/local/bin/taskflow
```

- `2770`: solo el grupo entra a la carpeta y todo lo nuevo queda del grupo.
- El grupo `docker` equivale a acceso de administrador del servidor: darlo solo a quien despliega.
- Cada persona necesita además **`sudo`** (el script lo usa para `.env` y Compose).

**B. Acceso a la imagen** para la persona nueva (sección anterior, pasos 1 y 2).

**C. Cada persona, con su usuario**: cerrar sesión y volver a entrar (los grupos nuevos solo
aplican en una sesión nueva), `id` debe incluir `docker`, `taskflow-admin` y `sudo`, hacer el
`docker login` y comprobar con `taskflow estado`.

### Script de despliegue `taskflow`

[`docker/desplegar.sh`](../docker/desplegar.sh), instalado como `/usr/local/bin/taskflow`. Es el de
mi-campus adaptado: solo toca el proyecto `taskflow-prod`, descarga antes de respaldar, valida el
respaldo con `pg_restore -l` antes de activar, espera a que `web` quede sano, prueba `/healthz/` y
avisa si cambió algún contenedor ajeno. Nunca usa `prune`, `down` ni `--remove-orphans`.

Se ejecuta **con el usuario propio**, nunca con `sudo` (el script pide `sudo` donde hace falta).
Para actualizarlo, copiarlo de nuevo con `scp` y repetir el `sudo install`.

| Comando | Qué hace |
| --- | --- |
| `taskflow estado` | Versión activa, contenedores, versiones descargadas, últimos respaldos y despliegues. |
| `taskflow desplegar <versión>` | Descarga → respalda base y archivos → cambia `.env` → `up -d` → espera a `healthy` → prueba `/healthz/` → compara contenedores ajenos. Si falla, muestra el comando exacto para volver. |
| `taskflow volver <versión> [respaldo.dump]` | Vuelve a una versión; con `.dump`, respalda lo actual y restaura la base (necesario si la versión que se deja aplicó migraciones). |
| `taskflow respaldar` | Solo respalda la base y los archivos. |
| `taskflow descargar <versión>` | Solo descarga la imagen. |
| `taskflow limpiar` | Borra versiones viejas de TaskFlow; conserva la activa y la anterior. |

Opciones: `--simular`, `--sin-media` y `--si` (no pide confirmación).

Los respaldos quedan en `/var/backups/taskflow/` con fecha, usuario y versión
(`taskflow_2026-10-01_153213_<usuario>_3104e6d.dump`), junto con `historial.log` y un candado que
impide dos despliegues a la vez. El script **no borra respaldos**: copiarlos fuera del servidor y
depurarlos a mano.

### Publicar y activar una versión sin el script (paso a paso)

```bash
cd /opt/taskflow
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | sort > ~/contenedores_antes.txt
sudo docker compose -f compose.prod.yaml exec -T db pg_dump -U taskflow -Fc taskflow > /var/backups/taskflow/taskflow_$(date +%F)_$(id -un).dump
grep TASKFLOW_IMAGE .env                                  # anotar la versión actual para volver
docker pull ghcr.io/ernestoas/taskflow:<versión>
sudo sed -i 's|^TASKFLOW_IMAGE=.*|TASKFLOW_IMAGE=ghcr.io/ernestoas/taskflow:<versión>|' .env
sudo docker compose -f compose.prod.yaml up -d
sudo docker compose -f compose.prod.yaml ps                # web: healthy
curl -s http://127.0.0.1:8082/healthz/
docker ps -a --format '{{.Names}}\t{{.Image}}\t{{.Status}}' | sort > ~/contenedores_despues.txt
diff ~/contenedores_antes.txt ~/contenedores_despues.txt  # solo debe cambiar taskflow-prod-web-1
```

Se usa siempre la etiqueta del commit, nunca `latest`: así `.env` dice qué versión corre y volver
atrás es cambiar esa línea (y restaurar la base si la versión nueva aplicó migraciones).

### Pasos propios de cada versión

Algunas versiones piden algo más que activar la imagen. **No son automáticos.** Quien integra un
cambio así lo anota aquí (y en §11 de la propuesta) en el mismo commit.

| Desde la versión | Qué hacer después de desplegar | Una vez o siempre |
| --- | --- | --- |
| *(primera versión)* | Primera instalación completa (sección de arriba) y `createsuperuser`. | Una vez |
| *(versión con proyectos, Etapa 2)* | **Antes:** agregar a `/opt/taskflow/.env.prod` `TASKFLOW_URL=https://sistemas.reduaz.mx/taskflow` y, para que las invitaciones lleguen, las `DJANGO_EMAIL_*` (ver `.env.prod.example`). **Después:** las tarjetas que ya existían quedan en el proyecto «Tarjetas anteriores» (migración `tarjetas.0004`); revisarlo en el admin y renombrarlo, moverlas o borrarlo. | Una vez |
| *(versión con la app, Etapa 3)* | Incluye los pasos de la Etapa 2 si no se hicieron. **Antes (opcional):** `TASKFLOW_REGISTRO_ABIERTO` y `TASKFLOW_LIMITE_ACCESO` en `.env.prod` (por omisión: registro abierto, 20 intentos/min). La imagen ya trae la PWA compilada; nginx no cambia (`/taskflow/` ya reenvía todo). **Después:** abrir `https://sistemas.reduaz.mx/taskflow/` (portada) y `/taskflow/app/`, crear una cuenta de prueba y revisar que `/taskflow/app/manifest.webmanifest` responda 200. | Una vez |
| *(versión con correo verificado, 2026-10-02)* | **Antes:** `DJANGO_EMAIL_*` y `DJANGO_DEFAULT_FROM_EMAIL` configuradas y probadas: **sin correo nadie puede terminar de registrarse** ni recuperar su contraseña. **Después:** la migración `usuarios.0002` separa `apellidos` en primer y segundo apellido y marca como verificadas las cuentas existentes; revisar en el admin los apellidos compuestos. | Una vez |

### Alternativa sin GitHub Actions

Si Actions no está disponible, construir en el equipo de quien despliega y enviar la imagen por
SSH; luego activar con `TASKFLOW_IMAGE=taskflow:<versión>` y sin `docker pull`:

```bash
VERSION=$(git rev-parse --short HEAD)       # desde main actualizado y sin cambios pendientes
docker build --target production -t taskflow:$VERSION .
docker save taskflow:$VERSION | gzip | ssh -p 4022 <usuario>@148.217.94.155 "gunzip | docker load"
```

## Respaldo manual

Al menos **semanal** y **antes de cada despliegue con migraciones** (`taskflow respaldar` lo hace;
a mano):

```bash
cd /opt/taskflow
sudo docker compose -f compose.prod.yaml exec -T db \
    pg_dump -U taskflow -Fc taskflow > /var/backups/taskflow/taskflow_$(date +%F)_<version>.dump
```

`-T` es obligatorio: sin él, `exec` usa una terminal que puede alterar el volcado binario. Guardar
los respaldos **fuera del servidor**.

Restaurar la base:

```bash
cd /opt/taskflow
sudo docker compose -f compose.prod.yaml stop web
sudo docker compose -f compose.prod.yaml exec -T db \
    pg_restore -U taskflow -d taskflow --clean --if-exists < /var/backups/taskflow/taskflow_<fecha>_<version>.dump
sudo docker compose -f compose.prod.yaml up -d
```

Respaldar también `.env.prod`, una vez, en un gestor de secretos: sin él el volcado es inservible
(se pierden la contraseña de PostgreSQL y la `DJANGO_SECRET_KEY`).

PostgreSQL **no se publica** (el 5432 del servidor es de actividades-uaz). Para conectarse desde
DBeaver o pgAdmin, usar un túnel SSH hacia el contenedor.
