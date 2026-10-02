# TaskFlow

Gestor de tarjetas para organizar actividades. Cada tarjeta tiene título, descripción, fecha de fin
opcional, uno o más asignados y uno de tres estatus: Pendiente → En curso → Finalizada.

- Stack: Python 3.13 · Django 5.2 LTS · DRF · PostgreSQL 18 · uv · Docker. PWA en `frontend/`:
  Vue 3 + Vite + TypeScript. Mismas convenciones que mi-campus.
- Diseño y esquema: [docs/propuesta-arquitectura.md](docs/propuesta-arquitectura.md).
  No crear modelos de dominio que no estén ahí.
- **El documento se actualiza en el mismo cambio, siempre** (ver §Sincronía con la propuesta).
- Operación en producción (primera instalación, despliegue, respaldos, vuelta atrás):
  [docs/operacion.md](docs/operacion.md). Producción: **https://sistemas.reduaz.mx/taskflow/**, en el
  mismo servidor que actividades-uaz y mi-campus. Inventario del montaje, configuraciones que
  existen solo por compartir y checklists para dominio propio o servidor propio:
  [docs/despliegue-actual.md](docs/despliegue-actual.md) (mantenerlo al día).
- Todo se ejecuta en Docker: la skill `taskflow-dev` tiene los comandos, las convenciones y la
  definición de terminado.
- Documentación de Django: skill `django-docs` (no responder de memoria sobre APIs de Django).
- Maquetas de diseño: [docs/_mockups/](docs/_mockups/); las v2 están aprobadas e implementadas
  (ver §Maquetas de diseño).
- Idioma: código de dominio, UI y commits en español.
- **No hacer commits automáticamente.** Al terminar un cambio, dejarlo sin commit para que yo
  revise el diff; solo hacer `git commit` (o `push`) cuando lo pida explícitamente.
- **Estado actual:** Etapas 1–3 listas: backend (proyectos, miembros, permisos, invitaciones,
  tipos e historial; §4.5), API `/api/v1/` (§6), PWA en `/app/` y portada de instalación en `/`
  (§5). En producción solo está la Etapa 1 (`f6d2e40`); ver «Pasos propios» en docs/operacion.md
  antes de desplegar.
- **Las reglas de negocio viven en `apps/<app>/servicios.py`.** Toda acción (también la API)
  pasa por esas funciones; nunca cambiar `Tarjeta.estatus` directamente, sino con
  `tarjetas.servicios.cambiar_estatus`, para que quede en el historial.

## Publicación bajo `/taskflow/` (reglas)

En producción TaskFlow no tiene dominio propio: vive en una ruta de `sistemas.reduaz.mx`
(`DJANGO_FORCE_SCRIPT_NAME=/taskflow`, ver docs/operacion.md). Para que eso no se rompa:

- Toda URL se genera con `{% url %}`, `reverse()`, `redirect("nombre")` o `{% static %}`;
  **nunca** rutas absolutas escritas a mano (`href="/tarjetas/"`, `fetch("/api/…")`), que en
  producción saltarían fuera de `/taskflow/` y caerían en actividades-uaz.
- `STATIC_URL` y `MEDIA_URL` se arman con `RUTA_BASE` (`/taskflow/static/`); no volverlas relativas
  (`static/`): con gunicorn quedan en caché sin el prefijo y el admin pierde los estilos.
- Las cookies tienen nombre propio (`taskflow_sessionid`, `taskflow_csrftoken`); en JS, leer el
  CSRF de `taskflow_csrftoken`, no de `csrftoken`.
- Lo que deba responder igual con o sin prefijo (como `/healthz/`) se compara contra
  `request.path_info`, no contra `request.path`.
- **PWA:** rutas con `#` (`createWebHashHistory`) y `base: "./"` en Vite; la API se llama siempre
  con `api("ruta/")` de `frontend/src/api.ts`, que calcula la raíz (`/app/` → `/api/v1/`,
  `/taskflow/app/` → `/taskflow/api/v1/`). Nunca `fetch("/api/…")` ni enlaces absolutos; para
  salir de la PWA a la portada, usar `RAIZ`.


## Sincronía con la propuesta de arquitectura

[docs/propuesta-arquitectura.md](docs/propuesta-arquitectura.md) es la **única fuente de verdad** del
diseño. Si el código y el documento no coinciden, el que está mal es el código.

**Regla: ningún cambio se considera terminado sin actualizar el documento en el mismo cambio.**
No en un commit posterior, no «cuando se estabilice»: en el mismo.

| Si cambió… | Actualizar |
|---|---|
| Un modelo, campo, restricción o validación | La sección del esquema (§4.x) donde vive ese modelo |
| Un modelo nuevo o eliminado | §3 (apps), §4.1 (diagrama ER) y su sección de §4.x |
| Una vista o pantalla | §5 |
| Un endpoint de API | §6 |
| Un flujo de acceso, permisos o seguridad | §7 |
| Algo que **contradice** lo aprobado | La sección correspondiente **y** una nota fechada en §11 que diga «Cambio al esquema aprobado» con el motivo |
| Una decisión de diseño con alternativas descartadas | §9, con el por qué del descarte (sirve para no reabrirla) |
| Una pregunta abierta que se resolvió | §10: marcarla resuelta con la fecha, sin borrarla |
| El estado de una etapa | §8 y el encabezado de estado del documento |

Además:

- **Anotar el razonamiento, no solo el resultado.** «`fecha_fin` es opcional» no sirve; «es opcional
  porque muchas actividades no tienen fecha comprometida y un valor inventado ensuciaría los
  vencimientos» sí.
- **Fechar las notas** (`(2026-10-01)`) y usar fechas absolutas, nunca «la semana pasada».
- Si algo se decidió pero **no** se implementó, va al documento marcado como *pendiente*.
- Si el documento resulta equivocado antes de tocar código, **corregirlo primero** y luego
  implementar.

## Estándar de interfaz

Toda la UI seguirá una paleta, componentes y patrones únicos. No inventar clases, colores ni
mecanismos propios; usar los que aquí se documentan y agregar aquí los nuevos **antes** de usarlos.

- **Identidad visual: navy + petróleo** (adoptada 2026-10-01; ese mismo día se retiró el coral, que se leía como alerta, y se descartó el azul por genérico). Guía, logo, ajustes de contraste y
  razones: [docs/identidad-visual.md](docs/identidad-visual.md). Variables `--tf-*` en
  [`static/css/tema.css`](static/css/tema.css), **fuente única** de los colores: **nunca hex
  sueltos** en templates ni en CSS de componentes. Si falta un color, se agrega ahí y en la guía.
- Reglas que más se olvidan: **rojo y ámbar solo para alertas** (vencida, urgente, eliminar, vence
  pronto); nada de coral ni naranja decorativo. Texto en petróleo con `--tf-accent-text`; sobre la barra
  navy, `--tf-accent-on-dark`; ante la duda, **neutro**.
- Logo en `static/img/marca/` (SVG navy y blanco); conserva su color propio `--tf-logo`.
- **Componentes de la PWA:** las clases de `frontend/src/estilos.css`, tomadas de la maqueta
  aprobada `app-v2.html` (`.btn-primario`, `.chip`, `.tarjeta`, `.hoja`, `.segmentos`, …). **Sin
  Bootstrap** (decidido 2026-10-01): la maqueta aprobada ya define cada componente con los `--tf-*`
  y Bootstrap solo agregaría peso y estilos que habría que deshacer. Un componente nuevo se agrega
  a `estilos.css` usando variables, nunca hex.
- **Portada** (`/`): plantilla de Django con `static/css/portada.css`, mismas variables.
- **Tipografía:** Inter desde `static/fonts/` vía `static/css/fuentes.css` (PWA y portada).
- Confirmaciones con `confirmar()` y avisos con `avisar()` de `frontend/src/ui.ts`; nunca
  `window.confirm`/`alert`.

### Jerarquía de botones (mapeo acción → clase)

| Acción | Clase | Ejemplo |
|---|---|---|
| Principal (guardar, crear, asignar) — navy con texto blanco | `btn btn-primario` | «Guardar», «Nueva tarjeta» |
| Secundaria (editar, filtrar, cancelar) | `btn btn-secundario` | «Editar», «Cancelar» |
| Destructiva (quitar, eliminar) | `btn btn-chico btn-peligro` (confirmación: `btn-peligro-lleno`) | «Eliminar», «Quitar» |
| Enlace / navegación | `btn btn-link` | «Ir a tarjetas» |

- «Cancelar» en formularios siempre es `btn-outline-secondary`, nunca `btn-link`.
- La misma acción lleva la misma clase en todo el sitio, sin excepciones.

### Mensajes al usuario

1. **Avisos (`avisar()` de `frontend/src/ui.ts`)**: confirman que una acción **ya ocurrió**
   («Se creó la tarjeta.», «Se movió a En curso.»). Texto plano, sin HTML ni emojis, verbo en
   pasado, una oración corta, sin signos de exclamación.
2. **Confirmaciones destructivas (`confirmar(mensaje, boton)` de `ui.ts`)**: toda acción que
   elimina, quita, cancela, archiva o transfiere pregunta antes nombrando lo afectado y la
   consecuencia («¿Eliminar la tarjeta «…»? Esta acción no se puede deshacer.»). Un solo diálogo
   en `App.vue`; nunca `window.confirm()` ni `alert()`.
3. **Validación de formularios**: las reglas y mensajes viven en los servicios (en español); la API
   los devuelve por campo (`{"titulo": ["…"]}`) y la vista los pinta bajo cada campo
   (`.campo .error`); lo general va en `.error-general`. No duplicar en Vue las reglas del
   servidor (solo lo mínimo, como «Escribe un título.»).

### Badges (estatus, prioridad, fecha)

Patrón único: **punto** con el color base, **texto** con la variante `-text` y **fondo** `-soft`.

| Significado | Variables |
|---|---|
| Pendiente | `--tf-status-pending*` (gris) |
| En curso | `--tf-status-progress*` (petróleo; texto `#155E75`) |
| Finalizada | `--tf-status-done*` (verde) |
| Prioridad baja · media · alta · urgente | `--tf-priority-{low,medium,high,urgent}*` (gris claro · gris · ámbar · rojo) |
| Vencida (fecha fin pasada, no finalizada) | `--tf-danger*` |
| Vence hoy / mañana | `--tf-warning*` |
| Tipo de tarjeta | color del usuario (`--tipo` en línea, mezclado con `color-mix()`) |

No inventar combinaciones fuera de esta tabla. **Urgente** además lleva un indicador lateral rojo
en la tarjeta; la tarjeta sigue blanca.

## Maquetas de diseño (`docs/_mockups/`)

Maquetas navegables para discutir interfaz **antes** de escribir código de vistas. Un archivo HTML
autocontenido por maqueta, con datos inventados y sin backend: se abre con doble clic.

| Archivo | Qué explora |
|---|---|
| `app-v2.html` | **Implementada** (con colores cambiados después: navy + petróleo, botón principal navy; ver docs/identidad-visual.md). Igual que v1 con la paleta navy + coral, el logo, la **prioridad** (badge, selector en el formulario, indicador lateral para urgente y orden por prioridad) y barra lateral navy en computadora. |
| `instalacion-v2.html` | **Implementada** (sin la ilustración del teléfono y con los colores nuevos). Portada de instalación con la paleta navy + coral y el logo. |
| `app-v1.html` | *(Reemplazada por v2; se conserva como referencia.)* PWA: mis proyectos (activos y archivados), tablero por estatus (pestañas en teléfono, tres columnas en computadora), detalle y edición de tarjeta, nueva tarjeta, miembros con permisos por persona, invitaciones, transferir/archivar/eliminar proyecto, «Mis tarjetas» y perfil. El escaparate cambia vista, usuario (Ana, dueña / Luis, miembro) y la fecha «de hoy». |
| `instalacion-v1.html` | *(Reemplazada por v2.)* Portada `https://sistemas.reduaz.mx/taskflow/`: qué es, botón «Instalar» y pasos por plataforma (Android, iPhone, computadora), primer acceso por invitación y preguntas frecuentes. El escaparate cambia el dispositivo y si la app ya está instalada. |

**Estado:** `app-v2.html` e `instalacion-v2.html` **aprobadas e implementadas** (2026-10-01) en
`frontend/` y `apps/core/templates/core/portada.html`; su CSS de componentes pasó a
`frontend/src/estilos.css`. La fuente de verdad ahora es la app y §5 de la propuesta. Una maqueta
nueva se agrega a la tabla de arriba y sus decisiones se listan aquí como *pendientes* hasta
aprobarse.

### Decisiones de las maquetas *(aprobadas e implementadas 2026-10-01)*

- **Tres pestañas: Proyectos · Mis tarjetas · Perfil.** «Mis tarjetas» reúne lo asignado a uno en
  todos sus proyectos, sin finalizadas, con las vencidas arriba y ordenado por fecha de fin.
- **Tablero:** en teléfono, una pestaña por estatus con su conteo (no tres columnas que no caben);
  en computadora, las tres columnas. Interruptor «Solo mías». Orden por fecha de fin, sin fecha al
  final.
- **Tipos de tarjeta** *(decidido 2026-10-01)*: cada proyecto tiene sus tipos (nombre único en el
  proyecto, descripción opcional y **color que elige el usuario**). Los crea, edita y elimina el
  dueño o quien tenga el permiso «Gestionar tipos» (quinto permiso, apagado de inicio). Una tarjeta
  puede tener **uno o más** tipos; se muestran como chips con su color en la tarjeta y el detalle, y
  el tablero se filtra por tipo. Eliminar un tipo lo quita de las tarjetas, no las borra.
- **Historial de estatus** *(decidido 2026-10-01)*: una tarjeta se puede mover entre los tres
  estatus en cualquier dirección, incluso después de finalizada. Cada cambio queda en el historial
  del detalle con **quién, de qué estatus a cuál, fecha y hora**; la creación es la primera entrada.
  Más reciente arriba.
- **El estatus se cambia desde el detalle** con tres botones; no hay arrastrar y soltar (en
  teléfono es torpe y no es accesible). Se puede agregar después en computadora.
- **Vencimiento visible:** tarjeta no finalizada con fecha pasada → badge «Vencida» en rojo;
  «Vence hoy» / «Vence mañana» en ámbar (tabla de badges de arriba). El borde lateral rojo queda
  reservado para la prioridad **urgente** (v2).
- **Prioridad** *(decidido 2026-10-01)*: baja, media (por omisión), alta, urgente; fija para todos los
  proyectos. En el tablero se ordena por prioridad y luego por fecha de fin.
- **Asignar a** *(decidido 2026-10-01)*: solo miembros del proyecto y **opcional**: hay tarjetas
  sin asignar (se muestran con «Sin asignar»).
- **Permisos** *(decidido 2026-10-01)*: el dueño siempre puede todo y es el **único** que invita,
  reenvía y cancela invitaciones y quita personas. **Crear, editar, cambiar estatus y eliminar**
  tarjetas son cuatro permisos que el **dueño asigna a cada miembro** (botones por persona en
  «Miembros y ajustes»); lo que no tiene permitido no aparece o sale deshabilitado. Quien acepta
  una invitación entra con **crear, editar y cambiar estatus** (sin eliminar).
- **Proyecto** *(decidido 2026-10-01)*: se puede **transferir** («Hacer dueño»: el anterior queda
  como miembro con todos los permisos), **archivar** (solo lectura para todos, aparece en
  «Archivados», se puede restaurar) y **eliminar** (con sus tarjetas, con confirmación). El dueño no
  puede salir sin transferir antes; un miembro sí puede salir. Quitar a alguien (o que salga) lo
  desasigna de las tarjetas del proyecto.
- **Invitación por correo** con enlace que **no vence** *(decidido 2026-10-01)*; si no tiene cuenta,
  la crea desde ahí y entra directo al proyecto. Las pendientes se ven y el dueño las **reenvía**
  (mismo enlace) o las cancela.
- **Dueño con la cuenta desactivada** sin haber transferido *(decidido 2026-10-01)*: un
  administrador transfiere el proyecto a otro miembro desde el admin de Django.
- **Instalación:** portada propia en `/taskflow/` con botón que usa `beforeinstallprompt` (Android
  y computadora) y pasos de Safari en iPhone; la app vive en `/taskflow/app/`. Igual que mi-campus.

### Convenciones de las maquetas

- Un solo archivo HTML autocontenido; sin dependencias locales (si hace falta una librería, por CDN).
- **Íconos SVG en línea, nunca emojis** (se ven distintos en cada dispositivo).
- Colores solo por variable CSS en `:root`; ningún hex suelto en el marcado. **Única excepción:**
  el color de un tipo de tarjeta, que es un **dato** elegido por el usuario: llega como
  `style="--tipo:#rrggbb"` y el CSS lo mezcla con `color-mix()` para el fondo y el texto del chip.
  En la app real se valida en el servidor (`^#[0-9a-f]{6}$`) antes de guardarlo.
- Si hace falta mostrar estados que dependen del tiempo (tarjeta vencida, por vencer), una barra
  superior de **escaparate de presentación** —que no es parte de la app— fija la fecha «de hoy».
  Se oculta en pantalla de teléfono.
- Datos de ejemplo inventados; nunca datos reales de personas.

**Antes de llevar cualquier decisión de una maqueta al código:** aprobarla y actualizar §5 de la
propuesta (y §6 si aparecen endpoints). La maqueta por sí sola no modifica el documento.

## Seguridad: HTML dinámico (regla de oro)

> **NUNCA armes HTML con f-strings interpolando datos del usuario (riesgo de XSS).**
> Usa siempre `render()` o `render_to_string()` con templates de Django.

| Función | Cuándo usarla |
|---|---|
| `render()` / `render_to_string()` | Siempre que se devuelva HTML (completo o parcial) |
| `format_html()` | Helpers puntuales (escapa automáticamente) |

Prohibido: `HttpResponse(f"...")` con datos del usuario, `mark_safe()` con datos no sanitizados,
construir HTML con concatenación o `.format()`, e inyectar `request.GET`/`request.POST` en HTML.

## Permisos y acceso a datos

- Toda vista que liste o modifique tarjetas filtra por lo que el usuario puede ver; nunca
  `Tarjeta.objects.all()` en una vista sin pensar quién la consulta.
- La API (`apps/api/`) deriva los datos de `request.user`; no acepta `usuario_id` arbitrario. Lo
  ajeno responde **404** (no 403), con `get_object_or_404` sobre lo visible para el usuario.
- Cada vista o endpoint nuevo lleva una prueba de acceso: un usuario sin permiso no puede leer ni
  modificar tarjetas ajenas.

---

## Modo «Solo reemplazo» (buscar y reemplazar manual)

Cuando yo escriba algo como **«activa modo solo reemplazo»** (o **«modo reemplazo»**, **«no toques
archivos»**), entras en este modo y permaneces en él hasta que yo diga explícitamente
**«desactiva modo solo reemplazo»** (o **«modo normal»**). Mientras esté activo:

- **NO** modifiques, crees ni elimines ningún archivo (no uses Edit, Write, ni equivalentes).
- **NO** ejecutes comandos que alteren el repo, la BD o los contenedores (nada de migraciones,
  pruebas, builds, `docker compose exec/run` que escriba). Los comandos de **solo lectura** sí
  están permitidos (p. ej. `docker compose exec web ruff check .` para verificar sin corregir).
- **SÍ** puedes **leer y buscar** en los archivos (Read, Grep, Glob) para localizar el código exacto.

En lugar de aplicar cambios, **entrégame parejas de bloques «buscar / reemplazar»** para que yo use
el **Ctrl+F → Reemplazar** de Visual Studio Code. Para cada cambio:

1. Indica el **archivo** (ruta relativa desde la raíz del proyecto) y, si ayuda, la línea aproximada.
2. Da el bloque **EXACTO tal como existe hoy** en el archivo (lo que pegaré en «Buscar»).
   Debe ser copiable literal: misma indentación, mismas comillas, sin números de línea ni adornos.
3. Da el bloque **por el que debo reemplazarlo** (lo que pegaré en «Reemplazar»).
4. El bloque «buscar» debe ser **único** en el archivo; si no lo es, amplíalo con líneas de contexto
   alrededor hasta que solo haya una coincidencia, y avísame.
5. Si un cambio toca varios lugares o varios archivos, numera cada pareja por separado.

Formato de cada pareja. **IMPORTANTE:** cada bloque de código va **suelto** (nunca envuelvas la
pareja completa en un bloque de 4 backticks ni anides bloques), para que el editor ponga un botón
de «copiar» independiente sobre cada recuadro y yo copie SOLO el código, sin el encabezado ni las
etiquetas. Escribe el encabezado y las etiquetas como texto normal, no dentro de un bloque:

Archivo: ruta/al/archivo.py (≈ línea N)

🔎 BUSCAR:

\```python
<código actual exacto>
\```

✅ REEMPLAZAR POR:

\```python
<código nuevo>
\```

Usa el indicador de lenguaje correspondiente (`python`, `html`, `css`, `typescript`…).

No expliques de más: ve directo a las parejas de bloques. Yo aplico los cambios manualmente.

**Archivos nuevos:** si hay que crear un archivo que no existe, en vez de buscar/reemplazar dame el
contenido completo con la ruta donde crearlo.

**Comandos pendientes:** al final de las parejas, lista los comandos que debo ejecutar después
(migraciones, pruebas, etc.), uno por bloque.
