# Guía para actualizar TaskFlow en producción

Para quien se suma a desplegar TaskFlow en el servidor de la UAZ (`sistemas.reduaz.mx`). Cubre la
configuración de una sola vez y cómo actualizar el sistema cada vez. El detalle técnico completo
está en `docs/operacion.md` del repositorio.

TaskFlow se publica en **https://sistemas.reduaz.mx/taskflow/**.

## Qué está automatizado y qué haces tú

```
Cambios en main  ──►  GitHub prueba y publica la imagen  ──►  Tú la instalas en el servidor
   (otra persona)          (automático, unos minutos)            (un comando: taskflow desplegar)
```

| Qué | ¿Quién o qué lo hace? |
| --- | --- |
| Probar el código y publicar la versión nueva | **GitHub, automático**, cada vez que alguien integra cambios en `main`. |
| Instalar la versión en el servidor | **Tú**, con `taskflow desplegar <versión>`. El servidor **nunca** se actualiza solo. |
| Respaldo previo, reinicio, migraciones y verificación | **El comando**, dentro de `taskflow desplegar`. |
| Pasos especiales de algunas versiones | **Tú, a mano**, solo si quien integró los cambios te dice que los hay. |
| Volver a la versión anterior | **Tú**, con el comando `taskflow volver …` que el propio script te muestra. |

## Parte 1. Configuración (una sola vez)

### 1.1 Lo que necesitas de quien administra el servidor

- [ ] **Tu usuario SSH** en el servidor (`148.217.94.155`, puerto `4022`).
- [ ] Que agregue tu usuario a los grupos **`docker`**, **`taskflow-admin`** y **`sudo`**.
- [ ] Que dé a **tu cuenta de GitHub** el rol *Read* sobre la imagen `taskflow` (cuenta
  `ErnestoAS`). Solo deja descargar la imagen: no da acceso al código.

### 1.2 Crear tu token de GitHub

Si ya tienes uno para mi-campus (classic, con `read:packages`) y no ha vencido, **sirve el mismo**:
salta a 1.3.

1. <https://github.com> → tu foto → **Settings** → **Developer settings**.
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**.
   Tiene que ser *classic*: el registro de imágenes no acepta los *fine-grained*.
3. **Note:** `servidor taskflow` · **Expiration:** 90 días (anota la fecha) · **Scopes:** solo
   **`read:packages`**.
4. **Generate token** y cópialo (empieza con `ghp_`). Guárdalo en un gestor de contraseñas.

### 1.3 Configurar tu usuario en el servidor

```bash
ssh -p 4022 <tu-usuario>@148.217.94.155
id                                  # debe incluir docker, taskflow-admin y sudo
read -rs GHCR_TOKEN                 # pega el token (no se ve) y Enter
echo "$GHCR_TOKEN" | docker login ghcr.io -u <tu-usuario-de-GitHub> --password-stdin
unset GHCR_TOKEN
taskflow estado
docker pull ghcr.io/ernestoas/taskflow:latest
```

Si `id` no muestra los grupos y ya te confirmaron que te agregaron, sal (`exit`) y vuelve a entrar.
`docker login` debe responder **`Login Succeeded`**, y el `docker pull` descargar sin errores (no
cambia nada en el sistema).

## Parte 2. Actualizar el sistema (cada vez)

### 2.1 Antes

1. **Conoce la versión.** Un código corto como `1dcd6b4`: te lo pasa quien integró los cambios, o
   lo ves en <https://github.com/ErnestoAS?tab=packages> → `taskflow` → la etiqueta más reciente
   que no sea `latest`.
2. **Pregunta si la versión tiene pasos especiales.**
3. **Elige el momento.** TaskFlow deja de responder unos segundos; actividades-uaz y mi-campus no
   se ven afectados.

### 2.2 Desplegar

```bash
ssh -p 4022 <tu-usuario>@148.217.94.155
taskflow estado                           # qué versión está activa ahora
taskflow desplegar <versión> --simular    # ensayo: no cambia nada
taskflow desplegar <versión>              # el despliegue real
```

- Ejecútalo **con tu usuario, sin `sudo`**. El comando pide tu contraseña cuando la necesita.
- Si otra persona está desplegando, el comando espera a que termine; no lo interrumpas.

Al final muestra la versión activa, dónde quedó el respaldo (`/var/backups/taskflow/`) y **el
comando exacto para volver atrás**: cópialo y guárdalo hasta confirmar que todo está bien.

### 2.3 Después

1. **Pasos especiales**, si la versión los tiene.
2. **Revisa en el navegador** <https://sistemas.reduaz.mx/taskflow/> e inicia sesión.
3. **Avisa** a quien integró los cambios que la versión ya está en producción.

## Si algo sale mal

**La versión nueva no arranca.** `taskflow desplegar` lo detecta, muestra los registros del error
y te da el comando para volver:

```bash
taskflow volver <versión-anterior> /var/backups/taskflow/taskflow_<fecha>_<usuario>_<versión>.dump
```

Regresa la versión anterior **y** la base de datos al momento del respaldo: lo capturado después se
pierde. Ante la duda, avisa antes de ejecutarlo.

| Mensaje | Qué pasa | Qué hacer |
| --- | --- | --- |
| `denied` al descargar | Token vencido o mal copiado, o tu cuenta no tiene acceso a la imagen | Crea otro token (1.2) y repite 1.3; si sigue, pide que confirmen tu rol *Read* |
| «No puedes escribir en /var/backups/taskflow» | Falta el grupo `taskflow-admin` o tu sesión es anterior a él | Sal y vuelve a entrar; si sigue, pide que te agreguen |
| «Tu usuario no puede usar docker» | Falta el grupo `docker` | Igual que el anterior |
| «Ejecútalo con tu usuario… no con sudo» | Lo ejecutaste con `sudo` | Ejecútalo sin `sudo` |
| «Versión no válida» | Código mal escrito | Son 7 caracteres: números y letras de la `a` a la `f` |

## Reglas del servidor

El servidor lo comparten **actividades-uaz, mi-campus y TaskFlow**. Para no afectar a las otras:

- Usa **solo** los comandos `taskflow …` de esta guía.
- **Nunca** ejecutes `docker system prune`, `docker image prune -a`, `docker volume prune`,
  `docker compose down -v` ni `docker compose up --remove-orphans`.
- Versiones viejas: `taskflow limpiar` (conserva la activa y la anterior).
- No borres archivos de `/var/backups/taskflow/`: son los respaldos de todo el equipo.
- No toques `/etc/nginx/` sin coordinarlo: el archivo de sitio es de actividades-uaz.
