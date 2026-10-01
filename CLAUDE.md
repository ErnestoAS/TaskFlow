# TaskFlow

Gestor de tarjetas para organizar actividades. Cada tarjeta tiene título, descripción, fecha de fin
opcional, uno o más asignados y uno de tres estatus: Pendiente → En curso → Finalizada.

- Stack: Python 3.13 · Django 5.2 LTS · PostgreSQL 18 · uv · Docker. Mismas convenciones que mi-campus.
- Diseño y esquema: [docs/propuesta-arquitectura.md](docs/propuesta-arquitectura.md).
  No crear modelos de dominio que no estén ahí.
- **El documento se actualiza en el mismo cambio, siempre** (ver §Sincronía con la propuesta).
- Operación en producción (primera instalación, despliegue, respaldos, vuelta atrás):
  [docs/operacion.md](docs/operacion.md). Producción: **https://sistemas.reduaz.mx/taskflow/**, en el
  mismo servidor que actividades-uaz y mi-campus.
- Todo se ejecuta en Docker: la skill `taskflow-dev` tiene los comandos, las convenciones y la
  definición de terminado.
- Documentación de Django: skill `django-docs` (no responder de memoria sobre APIs de Django).
- Maquetas de diseño (exploración, **no aprobadas**): [docs/_mockups/](docs/_mockups/)
  (ver §Maquetas de diseño).
- Idioma: código de dominio, UI y commits en español.
- **No hacer commits automáticamente.** Al terminar un cambio, dejarlo sin commit para que yo
  revise el diff; solo hacer `git commit` (o `push`) cuando lo pida explícitamente.
- **Estado actual: solo esqueleto** (modelos `Usuario` y `Tarjeta`, admin de Django y `/healthz/`).
  Aún no hay vistas, API ni frontend. CI y despliegue sí están listos.

## Publicación bajo `/taskflow/` (reglas)

En producción TaskFlow no tiene dominio propio: vive en una ruta de `sistemas.reduaz.mx`
(`DJANGO_FORCE_SCRIPT_NAME=/taskflow`, ver docs/operacion.md). Para que eso no se rompa:

- Toda URL se genera con `{% url %}`, `reverse()`, `redirect("nombre")` o `{% static %}`;
  **nunca** rutas absolutas escritas a mano (`href="/tarjetas/"`, `fetch("/api/…")`), que en
  producción saltarían fuera de `/taskflow/` y caerían en actividades-uaz.
- `STATIC_URL` y `MEDIA_URL` son relativas (`static/`) a propósito; no anteponerles `/`.
- Las cookies tienen nombre propio (`taskflow_sessionid`, `taskflow_csrftoken`); en JS, leer el
  CSRF de `taskflow_csrftoken`, no de `csrftoken`.
- Lo que deba responder igual con o sin prefijo (como `/healthz/`) se compara contra
  `request.path_info`, no contra `request.path`.


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

## Estándar de interfaz *(aplica cuando existan las vistas)*

Toda la UI seguirá una paleta, componentes y patrones únicos. No inventar clases, colores ni
mecanismos propios; usar los que aquí se documentan y agregar aquí los nuevos **antes** de usarlos.

- UI con **Bootstrap 5** (vía `django-bootstrap5` cuando se agreguen vistas).
- Colores solo por **variables CSS** en un archivo de tema (`static/css/tema.css`, por crear);
  **nunca hex sueltos** en templates ni en CSS de componentes.

### Jerarquía de botones (mapeo acción → clase)

| Acción | Clase | Ejemplo |
|---|---|---|
| Principal (guardar, crear, asignar) | `btn btn-primary` | «Guardar», «Asignar» |
| Secundaria (editar, filtrar, cancelar) | `btn btn-outline-secondary` | «Editar», «Cancelar» |
| Destructiva (quitar, eliminar) | `btn btn-sm btn-outline-danger` | «Eliminar», «Quitar» |
| Enlace / navegación | `btn btn-link` | «Ir a tarjetas» |

- «Cancelar» en formularios siempre es `btn-outline-secondary`, nunca `btn-link`.
- La misma acción lleva la misma clase en todo el sitio, sin excepciones.

### Mensajes al usuario

1. **Notificaciones (`django.contrib.messages`)**: confirman que una acción **ya ocurrió**
   («Tarjeta creada.», «No se pudo mover la tarjeta.»). Texto plano, sin HTML ni emojis, verbo en
   pasado, una oración corta, sin signos de exclamación.
2. **Confirmaciones destructivas (`data-confirmar`)**: todo `<form>` que elimina o quita lleva
   `data-confirmar="¿Eliminar la tarjeta «…»? Esta acción no se puede deshacer."`. Se resuelve con
   **un solo modal de Bootstrap** en el `base.html` y un listener delegado en JS; nunca
   `window.confirm()`, `onclick` ni JavaScript inline.
3. **Validación de formularios**: errores definidos en el modelo o el form, en español; se
   renderizan con `{% bootstrap_form %}` / `{% bootstrap_field %}` y
   `{% bootstrap_form_errors form type="non_fields" %}`. Nunca `<input>` manual.

### Badges de estatus de tarjeta

| Estatus | Clase Bootstrap |
|---|---|
| Pendiente | `text-bg-secondary` |
| En curso | `text-bg-info` |
| Finalizada | `text-bg-success` |
| Vencida (fecha fin pasada y no finalizada) | `text-bg-danger` |

No inventar combinaciones fuera de esta tabla.

## Maquetas de diseño (`docs/_mockups/`)

Maquetas navegables para discutir interfaz **antes** de escribir código de vistas. Un archivo HTML
autocontenido por maqueta, con datos inventados y sin backend: se abre con doble clic.

| Archivo | Qué explora |
|---|---|
| *(ninguna todavía)* | |

**Estado: exploración, nada de esto está aprobado ni implementado.** Las maquetas **no** son la
fuente de verdad y su CSS **no** se copia tal cual: la app usará Bootstrap 5 con las variables del
tema (ver §Estándar de interfaz), no clases propias. Cada maqueta nueva se agrega a la tabla de
arriba, y las decisiones que proponga se listan aquí como *pendientes de aprobación*.

### Convenciones de las maquetas

- Un solo archivo HTML autocontenido; sin dependencias locales (si hace falta una librería, por CDN).
- **Íconos SVG en línea, nunca emojis** (se ven distintos en cada dispositivo).
- Colores solo por variable CSS en `:root`; ningún hex suelto en el marcado.
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
| `{% bootstrap_form %}` / `{% bootstrap_field %}` | Renderizado de formularios |

Prohibido: `HttpResponse(f"...")` con datos del usuario, `mark_safe()` con datos no sanitizados,
construir HTML con concatenación o `.format()`, e inyectar `request.GET`/`request.POST` en HTML.

## Permisos y acceso a datos

- Toda vista que liste o modifique tarjetas filtra por lo que el usuario puede ver; nunca
  `Tarjeta.objects.all()` en una vista sin pensar quién la consulta.
- Una API (si se agrega) deriva los datos de `request.user`; no acepta `usuario_id` arbitrario.
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
