# TaskFlow — Operación en producción

Procedimientos del servidor Docker de producción (`compose.prod.yaml`). Diseño en
[propuesta-arquitectura.md](propuesta-arquitectura.md). **Inventario de cómo está montado hoy
(servidor, DNS, correo, lo configurado a mano) y checklists para agregar apps o mudarse:
[despliegue-actual.md](despliegue-actual.md).**

## Reparto de responsabilidades

| Capa | Quién | Qué hace |
| --- | --- | --- |
| Firewall de Hetzner | Consola de Hetzner | Solo deja entrar 22, 80, 443 e ICMP. |
| nginx del **servidor** (fuera de Docker) | Administración del servidor | Atiende 80/443, termina TLS con el certificado de `taskflow.rourendev.com` (certbot) y reenvía a `127.0.0.1:$TASKFLOW_HTTP_PORT` (8082). |
| `web` (gunicorn + WhiteNoise) | Este repositorio | Django. Sirve también los estáticos y la PWA. |
| `db` (PostgreSQL 18) | Este repositorio | No se publica fuera de Docker. |
| Correo saliente | Resend (SMTP) | Invitaciones y códigos de verificación y recuperación. |

No hay nginx interno: TaskFlow no tiene archivos privados que entregar con `X-Accel-Redirect`, y
WhiteNoise basta para los estáticos.

## Servidor

| Dato | Valor |
| --- | --- |
| Servidor | `srv-01` (Hetzner Cloud), Debian 13 · `178.105.178.16` |
| Acceso | SSH en el puerto **22**, solo con llave (`ssh leaguilar@taskflow.rourendev.com`, `scp … leaguilar@taskflow.rourendev.com:~/`) |
| Directorio | `/opt/taskflow` (`compose.prod.yaml`, `.env`, `.env.prod`) |
| Puerto de `web` | **8082** en loopback (`TASKFLOW_HTTP_PORT`), apartado en `/opt/PUERTOS.md` |
| URL pública | **https://taskflow.rourendev.com/** |
| Respaldos | `/var/backups/taskflow` (grupo `taskflow-admin`) |

El servidor está pensado para alojar **varias apps** (una por subdominio de `rourendev.com`). Hoy
solo tiene TaskFlow; cada app nueva aparta su puerto en `/opt/PUERTOS.md`
([despliegue-actual.md](despliegue-actual.md), checklist A). Por eso las reglas de «Qué toca y qué
no» aplican aunque hoy no haya otras.

### Los dos archivos de entorno

Son dos porque Compose resuelve dos cosas distintas, y **ninguna variable va en los dos**:

| Archivo | Quién lo lee | Qué contiene |
| --- | --- | --- |
| `.env.prod` | Los contenedores (`env_file:`) | Configuración de Django y PostgreSQL. Permisos `600`. |
| `.env` | Docker Compose | Solo `TASKFLOW_IMAGE` y `TASKFLOW_HTTP_PORT`, para interpolar `${...}` en `compose.prod.yaml`. |

`env_file:` no participa en la interpolación: poner `TASKFLOW_HTTP_PORT` en `.env.prod` no cambia el
puerto publicado. Si `.env` falta, Compose usa `taskflow:latest` (que no existe en el servidor) y
el arranque falla.

### Publicar bajo una ruta (no se usa hoy)

TaskFlow vive en la raíz de su dominio. El código también funciona bajo una ruta de otro dominio
(así estuvo en `sistemas.reduaz.mx/taskflow/` hasta 2026-10-03): el nginx de ese servidor quita el
prefijo (`location /taskflow/ { proxy_pass http://127.0.0.1:8082/; … }`, **con** diagonal final) y
`.env.prod` lleva `DJANGO_FORCE_SCRIPT_NAME=/taskflow`, para que Django lo anteponga en las URLs
que genera. Las cookies ya tienen nombre propio (`taskflow_sessionid`, `taskflow_csrftoken`) para
no pisar las de otra app del mismo dominio. Si el dominio tiene otros puertos en uso, HSTS se queda
en 0 (aplica a todo el dominio).

## Primera instalación

Una sola vez, en un servidor Debian 13 nuevo. Es lo que se hizo en `srv-01` del 2026-10-02 al
2026-10-03; los pasos de seguridad del servidor (1–3) sirven igual para cualquier otra app.

**1. Servidor y acceso.** En Hetzner: Debian 13, IPv4 e IPv6, tu llave SSH pública
(`ssh-keygen -t ed25519`) y un firewall con entrada solo para TCP 22, 80, 443 e ICMP. En el DNS
(Cloudflare): registros `A` y `AAAA` del subdominio, en **DNS only** (con la nube naranja certbot no
valida).

**2. Sistema y usuario** (como `root`, la primera vez):

```bash
apt update && apt full-upgrade -y
apt install -y sudo curl ca-certificates git nano htop
timedatectl set-timezone America/Mexico_City
hostnamectl set-hostname srv-01
adduser <usuario> && usermod -aG sudo <usuario>
install -d -m 700 -o <usuario> -g <usuario> /home/<usuario>/.ssh
install -m 600 -o <usuario> -g <usuario> /root/.ssh/authorized_keys /home/<usuario>/.ssh/
reboot
```

**3. Endurecer** (con el usuario propio; antes de recargar SSH, dejar abierta otra sesión):

```bash
printf 'PermitRootLogin no\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nPubkeyAuthentication yes\nAllowUsers <usuario>\n' | sudo tee /etc/ssh/sshd_config.d/00-endurecer.conf
sudo sshd -t && sudo systemctl reload ssh       # probar desde otra ventana antes de cerrar esta
sudo apt install -y fail2ban python3-systemd unattended-upgrades apt-listchanges
printf '[sshd]\nenabled = true\nbackend = systemd\nmaxretry = 5\nfindtime = 10m\nbantime = 1h\n' | sudo tee /etc/fail2ban/jail.d/sshd.local
sudo systemctl restart fail2ban
sudo dpkg-reconfigure -plow unattended-upgrades  # «Yes»
printf 'Unattended-Upgrade::Automatic-Reboot "true";\nUnattended-Upgrade::Automatic-Reboot-Time "04:00";\n' | sudo tee /etc/apt/apt.conf.d/52reinicio-automatico
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
echo 'vm.swappiness=10' | sudo tee /etc/sysctl.d/99-swap.conf && sudo sysctl --system
```

En Debian 13, fail2ban necesita `backend = systemd` (no hay `/var/log/auth.log`).

**4. Docker, nginx y certbot.** Docker desde su repositorio oficial (el de Debian no trae Compose
v2), con límite de logs:

```bash
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
printf 'Types: deb\nURIs: https://download.docker.com/linux/debian\nSuites: %s\nComponents: stable\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$(. /etc/os-release && echo "$VERSION_CODENAME")" | sudo tee /etc/apt/sources.list.d/docker.sources
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin nginx certbot python3-certbot-nginx
echo '{"log-driver": "json-file", "log-opts": {"max-size": "10m", "max-file": "3"}}' | sudo tee /etc/docker/daemon.json
sudo systemctl restart docker
sudo usermod -aG docker <usuario>               # equivale a administrador: solo a quien despliega
```

Sitio por omisión que corta lo que llegue por IP o por un dominio no configurado (Debian 13 ya trae
`server_tokens off`; no repetirlo o `nginx -t` falla con «duplicate»):

```bash
sudo rm /etc/nginx/sites-enabled/default
printf 'server {\n    listen 80 default_server;\n    listen [::]:80 default_server;\n    server_name _;\n    return 444;\n}\n' | sudo tee /etc/nginx/sites-available/00-por-omision
sudo ln -s /etc/nginx/sites-available/00-por-omision /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

**5. Carpetas, grupo, puerto y script** («Preparación para varias personas», más abajo), y apartar
el puerto en `/opt/PUERTOS.md`. Desde tu equipo, en la carpeta del repositorio:

```bash
scp docker/desplegar.sh compose.prod.yaml .env.prod.example docker/nginx/taskflow.conf leaguilar@taskflow.rourendev.com:~/
```

**6. Imagen y entorno.** Publicar la imagen (push a `main`, corrida en verde en *Actions*), hacer
`docker login ghcr.io` («Acceso a la imagen») y, en el servidor:

```bash
docker pull ghcr.io/ernestoas/taskflow:<versión>    # con tu usuario, sin sudo
sudo install -m 644 ~/compose.prod.yaml /opt/taskflow/
sudo install -m 600 ~/.env.prod.example /opt/taskflow/.env.prod
printf 'TASKFLOW_IMAGE=ghcr.io/ernestoas/taskflow:<versión>\nTASKFLOW_HTTP_PORT=8082\n' | sudo tee /opt/taskflow/.env
```

`taskflow descargar` todavía no sirve aquí: exige que ya existan `compose.prod.yaml` y `.env`.

**7. Secretos en `.env.prod`** sin que se vean en pantalla ni queden en el historial. Generar la
clave y la contraseña con `python3 -c "import secrets; print(secrets.token_urlsafe(50))"` (y `24`
para PostgreSQL) y guardarlas en un gestor de contraseñas **antes** de seguir; la API key de Resend
(*Sending access*, empieza con `re_`) también. Poner en `.env.prod.example` marcas como
`__CLAVE_PG__` en lugar de los valores, o editar con `sudo nano`, y luego:

```bash
read -rs CLAVE_PG; read -rs SECRET_KEY; read -rs RESEND_KEY      # pegar cada uno y Enter
sudo sed -i -e "s|__CLAVE_PG__|$CLAVE_PG|g" -e "s|__SECRET_KEY__|$SECRET_KEY|" -e "s|__RESEND_KEY__|$RESEND_KEY|" /opt/taskflow/.env.prod
unset CLAVE_PG SECRET_KEY RESEND_KEY
sudo grep -c "__" /opt/taskflow/.env.prod                         # 0: no quedó ninguna marca
```

La contraseña de PostgreSQL debe ser **la misma** en `POSTGRES_PASSWORD` y en `DATABASE_URL`, y se
fija **la primera vez** que arranca la base: cambiarla después en `.env.prod` no cambia la de la base
(fue la falla de la primera instalación en la UAZ, 2026-10-01).

**8. Levantar** (la primera vez con Compose directo: `taskflow desplegar` respalda antes, y aún no
hay base):

```bash
cd /opt/taskflow
sudo docker compose -f compose.prod.yaml up -d
sudo docker compose -f compose.prod.yaml ps                 # db y web: (healthy)
curl -s -H "Host: taskflow.rourendev.com" http://127.0.0.1:8082/healthz/   # {"status": "ok"}
sudo docker compose -f compose.prod.yaml exec web python manage.py createsuperuser
sudo docker compose -f compose.prod.yaml exec web python manage.py sendtestemail <tu-correo>
```

`sendtestemail` comprueba Resend: el correo debe llegar y verse como *Delivered* en
resend.com/emails.

**9. Publicarlo en nginx con HTTPS:**

```bash
sudo install -m 644 ~/taskflow.conf /etc/nginx/sites-available/taskflow
sudo ln -s /etc/nginx/sites-available/taskflow /etc/nginx/sites-enabled/taskflow
sudo nginx -t && sudo systemctl reload nginx
curl -s http://taskflow.rourendev.com/healthz/                # {"status": "ok"}
sudo certbot --nginx -d taskflow.rourendev.com --redirect     # correo para avisos; ToS: Y; EFF: N
sudo certbot renew --dry-run
```

Después, HSTS: `DJANGO_SECURE_HSTS_SECONDS=300` en `.env.prod`,
`sudo docker compose -f compose.prod.yaml up -d --force-recreate web` y comprobar
`curl -sI https://taskflow.rourendev.com/ | grep -i strict`. Si todo sigue bien unos días, subirlo a
`31536000` de la misma forma.

**10. Verificar:**

```bash
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' http://taskflow.rourendev.com/          # 301 https://…
curl -s https://taskflow.rourendev.com/healthz/                                                 # {"status": "ok"}
curl -s -o /dev/null -w '%{http_code}\n' https://taskflow.rourendev.com/app/manifest.webmanifest # 200
curl -s -o /dev/null -w '%{http_code} %{redirect_url}\n' https://taskflow.rourendev.com/django-admin/  # 302 …/login/
```

Y en el navegador: entrar al admin (se ve con estilos), registrarse en una ventana de incógnito con
un correo de prueba (un alias `+prueba` de Gmail sirve) y confirmar con el código, recuperar la
contraseña con otro código e instalar la app en el teléfono.

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
| Actualizar `compose.prod.yaml` o el sitio de nginx en el servidor | No | A mano, solo cuando cambian (el sitio instalado tiene además lo que agregó certbot: editarlo, no reemplazarlo). |
| Reinstalar el script `taskflow` | No | A mano, solo cuando cambia `docker/desplegar.sh`. |

Workflow: [`.github/workflows/publicar-imagen.yml`](../.github/workflows/publicar-imagen.yml).
Costo con repositorio privado en el plan Free: el límite son los **2,000 minutos al mes de
Actions** (compartidos con los demás repositorios de la cuenta); conviene juntar cambios en un
solo push.

### Qué toca y qué no

Los comandos `docker compose -f compose.prod.yaml …` actúan solo sobre el proyecto
`taskflow-prod` (fijado con `name:`). **Nunca** usar en este servidor (aloja o alojará otras apps):

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

Si la persona ya hizo `docker login ghcr.io` para otra imagen privada de la misma cuenta, **es la
misma credencial**: solo necesita además el rol Read sobre el paquete `taskflow`.

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
- Cada persona necesita además **`sudo`** (el script lo usa para `.env` y Compose) y estar en
  `AllowUsers` de `/etc/ssh/sshd_config.d/00-endurecer.conf` (`sudo sshd -t && sudo systemctl reload ssh`).

**B. Acceso a la imagen** para la persona nueva (sección anterior, pasos 1 y 2).

**C. Cada persona, con su usuario**: cerrar sesión y volver a entrar (los grupos nuevos solo
aplican en una sesión nueva), `id` debe incluir `docker`, `taskflow-admin` y `sudo`, hacer el
`docker login` y comprobar con `taskflow estado`.

### Script de despliegue `taskflow`

[`docker/desplegar.sh`](../docker/desplegar.sh), instalado como `/usr/local/bin/taskflow`. Solo toca el proyecto `taskflow-prod`, descarga antes de respaldar, valida el
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
depurarlos a mano (ver «Respaldo automático diario»).

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
| — | **La instalación en `srv-01` (2026-10-02) empezó en `3b54d39`**, que ya incluye todo lo de las tres filas siguientes: no hay que repetirlas ahí. Se conservan para instalaciones que vengan de versiones viejas. | — |
| *(versión con proyectos, Etapa 2)* | **Antes:** agregar a `/opt/taskflow/.env.prod` `TASKFLOW_URL` (la URL pública) y, para que las invitaciones lleguen, las `DJANGO_EMAIL_*` (ver `.env.prod.example`). **Después:** las tarjetas que ya existían quedan en el proyecto «Tarjetas anteriores» (migración `tarjetas.0004`); revisarlo en el admin y renombrarlo, moverlas o borrarlo. | Una vez |
| *(versión con la app, Etapa 3)* | Incluye los pasos de la Etapa 2 si no se hicieron. **Antes (opcional):** `TASKFLOW_REGISTRO_ABIERTO` y `TASKFLOW_LIMITE_ACCESO` en `.env.prod` (por omisión: registro abierto, 20 intentos/min). La imagen ya trae la PWA compilada; nginx no cambia. **Después:** abrir la portada y `/app/`, crear una cuenta de prueba y revisar que `/app/manifest.webmanifest` responda 200. | Una vez |
| *(versión con correo verificado, 2026-10-02)* | **Antes:** `DJANGO_EMAIL_*` y `DJANGO_DEFAULT_FROM_EMAIL` configuradas y probadas: **sin correo nadie puede terminar de registrarse** ni recuperar su contraseña. **Después:** la migración `usuarios.0002` separa `apellidos` en primer y segundo apellido y marca como verificadas las cuentas existentes; revisar en el admin los apellidos compuestos. | Una vez |
| *(versión con pizarras y listas, Etapa 3.6, 2026-10-05)* | **Nada a mano para migrar:** al arrancar, el `migrate` de `apps.core` pasa la app `proyectos` a `pizarras` (tablas, `django_migrations` y `django_content_type`, en una transacción; en el registro de `web` sale «La app «proyectos» pasó a «pizarras»») y luego `pizarras.0002`–`0003` y `tarjetas.0007`–`0009` crean las listas «Pendiente», «En curso» y «Finalizada» de cada pizarra y acomodan cada tarjeta según su estatus. **Antes:** confirmar que `taskflow desplegar` tomó el respaldo (esta versión cambia mucho el esquema). **Después:** abrir una pizarra en `/app/` y revisar que sus tarjetas estén en sus listas; las PWA instaladas se actualizan solas en 15 s (la versión vieja no habla con la API nueva). **Vuelta atrás:** solo restaurando ese respaldo y la imagen anterior; revertir migraciones deja la etiqueta `pizarras`, que el código anterior no reconoce. | Una vez |

### Alternativa sin GitHub Actions

Si Actions no está disponible, construir en el equipo de quien despliega y enviar la imagen por
SSH; luego activar con `TASKFLOW_IMAGE=taskflow:<versión>` y sin `docker pull`:

```bash
VERSION=$(git rev-parse --short HEAD)       # desde main actualizado y sin cambios pendientes
docker build --target production -t taskflow:$VERSION .
docker save taskflow:$VERSION | gzip | ssh leaguilar@taskflow.rourendev.com "gunzip | docker load"
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

PostgreSQL **no se publica** (solo `web` lo alcanza, por la red interna de Compose). Para
conectarse desde DBeaver o pgAdmin, usar un túnel SSH hacia el contenedor.

## Respaldo automático diario *(listo, sin instalar)*

**Hoy no está instalado** (decisión de 2026-10-03, ver despliegue-actual.md §4): los únicos
respaldos son los de `taskflow`, dentro del mismo servidor. Copiarlos a tu equipo tras cada
despliegue:

```powershell
scp "leaguilar@taskflow.rourendev.com:/var/backups/taskflow/*" C:\respaldos\taskflow\
```

Para instalarlo: [`docker/respaldo-diario.sh`](../docker/respaldo-diario.sh) respalda base y
archivos en `/var/backups/taskflow/diarios/` y borra los de más de 14 días; lo dispara
[`docker/systemd/taskflow-respaldo.timer`](../docker/systemd/taskflow-respaldo.timer) a las 03:30
(antes de los reinicios de las 04:00). Corre como root, por eso no usa el comando `taskflow`.

```bash
scp docker/respaldo-diario.sh docker/systemd/taskflow-respaldo.* leaguilar@taskflow.rourendev.com:~/   # desde tu equipo
sudo install -m 750 ~/respaldo-diario.sh /usr/local/sbin/taskflow-respaldo-diario
sudo install -m 644 ~/taskflow-respaldo.service ~/taskflow-respaldo.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start taskflow-respaldo.service          # prueba: status=0/SUCCESS y archivos en diarios/
cat /var/backups/taskflow/diarios/registro.log
sudo systemctl enable --now taskflow-respaldo.timer
systemctl list-timers taskflow-respaldo.timer --no-pager
```

Siguen dentro del mismo servidor: para sobrevivir a la pérdida del servidor hace falta además una
copia fuera (Backups de Hetzner, +20 %, o bajarlos a mano).
