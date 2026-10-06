# TaskFlow — Cómo está montado hoy

> **Fecha:** 2026-10-05 · **Versión activa:** `90939ed` en `srv-01` (Hetzner), desde el 2026-10-05 (antes `3b54d39`).
> Este documento es el **inventario** del despliegue: qué hay en el servidor, qué se configuró a
> mano fuera de `/opt/taskflow` y qué hacer para agregar otra app o mudar TaskFlow de servidor.
> Procedimientos (instalar, desplegar, respaldar, volver atrás): [operacion.md](operacion.md).
> **Mantenerlo al día** cada vez que se toque el servidor.

---

## 1. Situación actual

| Dato | Valor |
| --- | --- |
| URL pública | **https://taskflow.rourendev.com/** (app: `/app/`, admin: `/django-admin/`) |
| Servidor | `srv-01` · Hetzner Cloud, proyecto `personal` · Debian 13 · 2 vCPU, 4 GB de RAM, 40 GB de disco · centro de datos en Europa (ver consola) |
| IP | IPv4 `178.105.178.16` · IPv6 `2a01:4f8:1c16:7dcf::1` |
| SSH | Puerto **22**, solo con llave y solo el usuario `leaguilar` (`ssh leaguilar@taskflow.rourendev.com`) |
| Dominio y DNS | `rourendev.com` en **Cloudflare** (registro y DNS). `taskflow` → registros `A` y `AAAA`, **DNS only** (nube gris) |
| Correo | **Resend** (dominio `rourendev.com` verificado, región us-east-1), SMTP `smtp.resend.com:587`. Remitente `no-responder@rourendev.com` |
| Repositorio | `github.com/ErnestoAS/TaskFlow` (**privado**) |
| Imagen | `ghcr.io/ernestoas/taskflow:<commit corto>` (privada; la publica GitHub Actions) |
| Directorio | `/opt/taskflow` (`compose.prod.yaml`, `.env`, `.env.prod`) |
| Proyecto de Compose | `taskflow-prod` (contenedores `taskflow-prod-db-1` y `taskflow-prod-web-1`) |
| Volúmenes | `taskflow-prod_db-data`, `taskflow-prod_media` |
| Puerto | `web` publicado solo en **`127.0.0.1:8082`**; PostgreSQL **sin publicar** |
| Certificado | Let's Encrypt propio de `taskflow.rourendev.com` (certbot, renovación automática con `certbot.timer`) |
| HSTS | `max-age=300` desde 2026-10-02; **pendiente** subirlo a `31536000` |
| Comando de despliegue | `/usr/local/bin/taskflow` (copia de `docker/desplegar.sh`) |
| Respaldos | `/var/backups/taskflow/` (grupo `taskflow-admin`, `2770`), solo los que hace `taskflow`. **Sin respaldo diario ni copia fuera del servidor** (ver §4) |

```
Internet ──80/443──► firewall de Hetzner (solo 22, 80, 443 e ICMP)
                       └─► nginx de srv-01 (certificado por subdominio)
                             ├─ taskflow.rourendev.com ─► 127.0.0.1:8082  TaskFlow (gunicorn + WhiteNoise) ─► db (sin publicar)
                             └─ IP directa u otro nombre ─► 444 (se corta sin responder)
```

Hasta el **2026-10-03**, TaskFlow vivió en `https://sistemas.reduaz.mx/taskflow/`, en el servidor
de la UAZ que comparten actividades-uaz y mi-campus. Ver §6.

## 2. Lo que se hizo en el servidor (inventario)

Todo lo que existe fuera de `/opt/taskflow`, para saber qué rehacer al mudarse o qué limpiar.

| Qué | Dónde | Notas |
| --- | --- | --- |
| Firewall de Hetzner `web-basico` | Consola de Hetzner | Entrada: TCP 22, 80, 443 e ICMP. Salida: todo. Los puertos de las apps (8082…) **no** se abren |
| Usuario `leaguilar` | grupos `sudo`, `docker`, `taskflow-admin` | Contraseña solo para `sudo`; entra por llave SSH |
| SSH endurecido | `/etc/ssh/sshd_config.d/00-endurecer.conf` | `PermitRootLogin no`, sin contraseñas, `AllowUsers leaguilar`. **Al dar acceso a otra persona, agregarla a `AllowUsers`** |
| fail2ban | `/etc/fail2ban/jail.d/sshd.local` | `backend = systemd`, 5 intentos en 10 min → 1 h bloqueada |
| Actualizaciones automáticas | `unattended-upgrades` + `/etc/apt/apt.conf.d/52reinicio-automatico` | Solo seguridad; reinicia a las **04:00** si hace falta (las apps vuelven por `restart: unless-stopped`) |
| Swap | `/swapfile` (2 GB) en `/etc/fstab`; `/etc/sysctl.d/99-swap.conf` (`vm.swappiness=10`) | Hetzner no trae swap |
| Zona horaria y nombre | `America/Mexico_City`, `srv-01` | |
| Docker | Repositorio oficial (`/etc/apt/sources.list.d/docker.sources`) | `/etc/docker/daemon.json`: logs de 10 MB × 3 por contenedor |
| nginx y certbot | Paquetes de Debian | `server_tokens off` ya viene en el `nginx.conf` de Debian 13 |
| Sitio por omisión | `/etc/nginx/sites-available/00-por-omision` (enlazado) | `return 444` a la IP y a dominios no configurados; se quitó el `default` de Debian |
| Sitio de TaskFlow | `/etc/nginx/sites-available/taskflow` (enlazado) | Copia de `docker/nginx/taskflow.conf` **más** lo que agregó certbot (443 y redirección) |
| Registro de puertos | `/opt/PUERTOS.md` | Apartar ahí el puerto de cada app nueva |
| Grupo | `taskflow-admin` | |
| Carpeta de respaldos | `/var/backups/taskflow` (root:`taskflow-admin`, `2770`) | |
| Script | `/usr/local/bin/taskflow` | Se reinstala cuando cambia `docker/desplegar.sh` |
| Variable del script | `/etc/profile.d/taskflow.sh` (`TASKFLOW_HOST_SALUD=taskflow.rourendev.com`) | Ya no hace falta desde que es el valor por omisión del script; se puede borrar |
| Login de ghcr.io | `~leaguilar/.docker/config.json` | Token *classic* `read:packages` «srv-01 hetzner – leer imagen taskflow», vence en un año (fecha sugerida: **2027-10-02**; confirmar en GitHub → Settings → Tokens) |

## 3. Variables que dependen de este montaje

| # | Variable o ajuste | Dónde | Valor | Al mudarse o cambiar de dominio |
| --- | --- | --- | --- | --- |
| 1 | `DJANGO_ALLOWED_HOSTS` | `.env.prod` | `taskflow.rourendev.com,localhost,127.0.0.1` | Cambiar el dominio |
| 2 | `DJANGO_CSRF_TRUSTED_ORIGINS` | `.env.prod` | `https://taskflow.rourendev.com` | Cambiar el dominio |
| 3 | `TASKFLOW_URL` | `.env.prod` | `https://taskflow.rourendev.com` | Cambiar; las invitaciones ya enviadas dejan de funcionar salvo con redirección |
| 4 | `DJANGO_FORCE_SCRIPT_NAME` | `.env.prod` | vacío | Solo si se publica bajo una ruta de otro dominio |
| 5 | `DJANGO_EMAIL_*`, `DJANGO_DEFAULT_FROM_EMAIL` | `.env.prod` | Resend | Igual en otro servidor; si cambia el dominio de correo, verificarlo en Resend |
| 6 | `DJANGO_SECURE_HSTS_SECONDS` | `.env.prod` | `300` | Subir a `31536000` cuando se confirme |
| 7 | `GUNICORN_CMD_ARGS` | `.env.prod` | 3 workers | Ajustar a los núcleos y a cuántas apps compartan |
| 8 | Puerto **8082** | `/opt/taskflow/.env`, defaults de `compose.prod.yaml`, `docker/nginx/taskflow.conf`, `docker/desplegar.sh` | 8082 | Si cambia, en los **cuatro** lugares y en `/opt/PUERTOS.md` |
| 9 | `HOST_SALUD` | `docker/desplegar.sh` | `taskflow.rourendev.com` | Cambiar el dominio |
| 10 | Registros DNS | Cloudflare | `taskflow` A/AAAA; `send` MX/TXT, `resend._domainkey` TXT y `_dmarc` TXT (Resend) | Apuntar `taskflow` a la IP nueva |

La PWA no depende del dominio (rutas con `#`, `base: "./"`, la raíz de la API se calcula de la
URL). Si cambia el dominio, los usuarios deben **reinstalar** la app.

Para encontrar todas las menciones en el repositorio:

```bash
grep -rn "rourendev\|178.105.178.16\|8082" --exclude-dir=.git --exclude-dir=node_modules .
```

## 4. Riesgos aceptados *(2026-10-03, Ernesto)*

- **Sin respaldo diario automático ni Backups de Hetzner** (cuestan 20 % más). Los únicos
  respaldos son los de `taskflow desplegar` / `taskflow respaldar`, **dentro del mismo servidor**:
  si el servidor se pierde, se pierden con él. Mitigación a mano: tras cada despliegue,
  `scp "leaguilar@taskflow.rourendev.com:/var/backups/taskflow/*" C:\respaldos\taskflow\`.
  El respaldo diario ya está listo en el repositorio (`docker/respaldo-diario.sh` y
  `docker/systemd/`), **sin instalar**; instalarlo cuando haya usuarios reales
  (operacion.md, «Respaldo automático diario»).
- **Una sola persona con acceso SSH.** Si se pierde la llave, se entra por la consola web de
  Hetzner (servidor → *Console*) con la contraseña de `leaguilar`.

## 5. Checklists

### A. Agregar otra app en este servidor

1. Apartar un puerto en `/opt/PUERTOS.md` (siguientes libres: 8083, 8084…).
2. Grupo `<app>-admin`, `/opt/<app>` (root, `755`) y `/var/backups/<app>` (`2770`), como TaskFlow.
3. Su `compose` con `name:` propio, `web` publicado solo en `127.0.0.1:<puerto>` y su base sin
   publicar.
4. Registro `A`/`AAAA` del subdominio en Cloudflare (nube gris) apuntando a `178.105.178.16`.
5. Su sitio en `/etc/nginx/sites-available/<app>` (como `docker/nginx/taskflow.conf`), `nginx -t`,
   recargar y `certbot --nginx -d <sub>.rourendev.com --redirect`.
6. Revisar la RAM (`free -h`): con varias apps, bajar workers o subir de plan en Hetzner.
7. **Nunca** `docker system prune` ni `docker volume prune`: ya hay más de una app.

### B. Mudar TaskFlow a otro servidor

1. Preparar el servidor nuevo con los pasos 1–7 de «Primera instalación» de operacion.md.
2. Copiar `/opt/taskflow/.env.prod` **tal cual** (tiene la `DJANGO_SECRET_KEY` y la contraseña de
   PostgreSQL; sin ellas el respaldo no sirve) y `/opt/taskflow/.env`.
3. Ventana de mantenimiento en el viejo: `taskflow respaldar` y
   `sudo docker compose -f compose.prod.yaml stop web`.
4. Copiar el `.dump` y el `media_*.tar.gz` al nuevo y restaurar:

   ```bash
   cd /opt/taskflow
   docker pull ghcr.io/ernestoas/taskflow:<versión activa>
   sudo docker compose -f compose.prod.yaml up -d db
   sudo docker compose -f compose.prod.yaml exec -T db pg_restore -U taskflow -d taskflow --clean --if-exists < taskflow_<...>.dump
   sudo docker run --rm -v taskflow-prod_media:/m -v "$PWD":/r alpine tar xzf /r/media_<...>.tar.gz -C /
   sudo docker compose -f compose.prod.yaml up -d
   ```

5. Cambiar en Cloudflare la IP de `taskflow` y, cuando resuelva, `certbot --nginx` en el nuevo.
6. Verificar (operacion.md, paso 9 de «Primera instalación») y, cuando esté confirmado, apagar el
   viejo con `down` **sin `-v`**; borrar sus volúmenes a mano después.
7. Actualizar este documento.

## 6. Historia: el servidor de la UAZ (hasta 2026-10-03)

Del 2026-10-01 al 2026-10-03, TaskFlow (solo la Etapa 1, versión `f6d2e40`) estuvo en
`https://sistemas.reduaz.mx/taskflow/`, en el servidor de la UAZ (148.217.94.155, SSH 4022), como
ruta del sitio de actividades-uaz (`include` de un snippet de nginx) y con
`DJANGO_FORCE_SCRIPT_NAME=/taskflow`. Se mudó porque no se podían pedir más dominios, porque
compartir servidor obligaba a restricciones (sin HSTS, 2 workers, puertos y cookies con nombre
propio) y porque Ernesto quiere publicar sus propias apps (propuesta, §9).

**Retiro (2026-10-03):** no se conservaron datos (solo había la Etapa 1, sin usuarios). Se recargó
nginx sin TaskFlow (el `include` ya se había quitado del archivo el 2026-10-01 a las 14:02, sin
recargar, y el archivo quedó idéntico a su copia previa), se borró el snippet, se apagaron y
eliminaron los contenedores, imágenes, volúmenes, `/opt/taskflow`, `/var/backups/taskflow`,
`/usr/local/bin/taskflow` y el grupo `taskflow-admin`. Quedan en `~leaguilar` dos copias del sitio
de actividades-uaz (`gestioneducativa.antes-de-taskflow` y `.antes-de-quitar-taskflow`). Se
comprobó que actividades-uaz y mi-campus siguieron funcionando.

El código sigue soportando publicarse bajo una ruta (`DJANGO_FORCE_SCRIPT_NAME`, cookies con nombre
propio, PWA con rutas `#`): ver operacion.md, «Publicar bajo una ruta».
