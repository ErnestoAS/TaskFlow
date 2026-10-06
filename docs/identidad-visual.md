# TaskFlow — Identidad visual y paleta

> **Estado:** adoptada el 2026-10-01 a partir de la guía «TaskFlow — sistema visual y paleta de
> colores» de Ernesto, con los ajustes de accesibilidad de la sección 3. Variables en
> [`static/css/tema.css`](../static/css/tema.css); maquetas que la aplican:
> [`docs/_mockups/app-v2.html`](_mockups/app-v2.html) y
> [`docs/_mockups/instalacion-v2.html`](_mockups/instalacion-v2.html).
>
> **Cambio del 2026-10-01 (Ernesto): se retira el coral.** Se leía como rojo, es decir, como alerta
> o error. Se probó azul (`#2563EB`) y se descartó por parecerse al de todas las apps. El acento
> queda en **petróleo** (`--tf-accent` `#0E7490`): «En curso», pestaña activa e indicadores. La
> prioridad baja y media pasan a grises (media, la de omisión, es neutra) y el botón principal es
> navy con texto blanco. **El rojo y el ámbar quedan solo para lo que sí es alerta** (vencida,
> urgente, eliminar, vence pronto). Las maquetas v2 conservan el coral como registro histórico.

## 1. Idea

TaskFlow se reconoce por **navy + petróleo + blanco** sobre un gris muy claro. La modernidad viene de
la jerarquía, el espaciado, la tipografía y el uso **controlado** del color, no de gradientes,
sombras ni muchos colores. **Ante la duda, neutro.**

| Color | Función |
| --- | --- |
| Navy `#172554` | Identidad, navegación, estructura (barra lateral, títulos, botón de navegación activo). |
| Petróleo `#0E7490` | Acento: progreso («En curso»), seleccionado, indicadores. Nunca como fondo de áreas grandes. (Antes coral `#F97360`, retirado el 2026-10-01.) |
| Verde | Finalizada / éxito. |
| Azul | Información (avisos neutros). |
| Ámbar | Advertencia / prioridad alta / «vence pronto». |
| Rojo | Urgente / vencida / error. |
| Grises | Pendiente, prioridad baja y media, metadatos, texto secundario. |

## 2. Logo

Archivos en `static/img/marca/` (vectorizados de los PNG originales, que también están ahí):

| Archivo | Uso |
| --- | --- |
| `taskflow-simbolo.svg` | Símbolo (flujo + check). Cabecera en teléfono, ícono, favicon. |
| `taskflow-logo.svg` | Símbolo + «TaskFlow». Portada, correos, documentos. |
| `taskflow-simbolo-blanco.svg`, `taskflow-logo-blanco.svg` | Sobre navy (barra lateral). |

El logo usa su propio navy **`#000955`** (`--tf-logo`), un poco más oscuro que el navy de la interfaz
(`#172554`). Se respeta: el logo no cambia de color salvo su versión blanca. Íconos de la PWA (192, 512
y *maskable*, símbolo navy sobre blanco) en `frontend/public/iconos/`, generados de
`taskflow-simbolo.svg`.

## 3. Ajustes a la guía original (y por qué)

Se midió el contraste de cada par texto/fondo con el criterio WCAG AA (mínimo 4.5:1 para texto
normal). Cuatro combinaciones de la guía no pasaban; se corrigieron **sin cambiar los colores de
marca**, solo cómo se usan:

| Caso | Guía original | Contraste | Ajuste adoptado | Contraste |
| --- | --- | --- | --- | --- |
| Botón principal | Blanco sobre coral | 2.75 ✗ | **Botón navy con texto blanco** (`--tf-btn`, `--tf-on-btn`; cambio de Ernesto, 2026-10-01; el acento queda para indicadores) | 14.6 ✓ |
| Badge «En curso» | Coral sobre coral suave | 2.48 ✗ | Petróleo: texto `#155E75` sobre `#ECFEFF`, punto `#0E7490` | 6.99 ✓ |
| Badge «Finalizada» | `#16A34A` sobre verde suave | 3.13 ✗ | Texto `#15803D`; el verde queda en el punto | 4.76 ✓ |
| Navegación activa | Coral sobre coral 10 % | ✗ | Texto navy (o blanco en la barra navy) + barra indicadora cian claro (`#67E8F9` sobre navy) | ✓ |

Otras decisiones:

- **Prioridad alta en ámbar `#D97706`, no naranja `#F97316`.** El naranja y el coral tienen un
  contraste entre sí de 1.02: son indistinguibles, y una tarjeta en curso con prioridad alta se
  vería de un solo color.
- **Prioridad** es un campo fijo de la tarjeta (baja, media, alta, urgente; por omisión media),
  decidido el 2026-10-01. Urgente se marca con un **indicador lateral rojo**; la tarjeta sigue
  blanca. Desde el 2026-10-05 el orden dentro de cada lista es manual (se arrastra).
- **Los tipos no son fijos:** cada pizarra crea los suyos (§4.5 de la propuesta). Los seis colores
  de la guía (desarrollo, reunión, soporte, mantenimiento, diseño, administración) son los
  **colores sugeridos** del selector; el usuario puede elegir otro.
- **Avatares** en escala navy/pizarra, sin colores extra.
- **Inter** se sirve desde TaskFlow (`static/fonts/`, subconjuntos latín y latín extendido de
  `@fontsource-variable/inter`, licencia OFL en `static/fonts/OFL.txt`; declarada en
  `static/css/fuentes.css`), no desde Google Fonts: la app instalada debe verse igual sin conexión y
  no depender de terceros. La PWA y la portada importan el mismo archivo. Las maquetas sí la cargan
  de Google Fonts.

## 4. Variables

Todas en `static/css/tema.css`. Resumen:

| Grupo | Variables |
| --- | --- |
| Marca | `--tf-logo`, `--tf-primary`, `--tf-primary-hover`, `--tf-primary-soft`, `--tf-accent`, `--tf-accent-hover`, `--tf-accent-soft`, `--tf-accent-text`, `--tf-on-accent`, `--tf-accent-on-dark` (indicadores sobre la barra navy) |
| Botón principal | `--tf-btn` `#172554`, `--tf-btn-hover` `#1E3A8A`, `--tf-on-btn` `#FFF` |
| Base | `--tf-bg` `#F5F7FA`, `--tf-surface` `#FFF`, `--tf-text` `#172033`, `--tf-text-muted` `#64748B`, `--tf-text-disabled`, `--tf-border` `#E2E8F0`, `--tf-sidebar-text` |
| Éxito | `--tf-success` `#16A34A`, `--tf-success-text` `#15803D`, `--tf-success-soft` `#ECFDF5`: checklist completa y marca de lista de cierre (2026-10-05). Reemplaza a `--tf-status-*`, que se fueron con los estatus: las listas no tienen color (su chip es navy suave, `--tf-primary-soft`/`--tf-primary`). |
| Semánticos | `--tf-{danger,warning,info}`, `…-text`, `…-soft` |
| Prioridad | `--tf-priority-{low,medium,high,urgent}`, `…-text`, `…-soft` |
| Forma | `--tf-radius-card` 12px, `--tf-radius-btn` 9px, `--tf-radius-modal` 16px, `--tf-shadow`, `--tf-shadow-float` |

Patrón de **badge**: punto con el color base, texto con la variante `-text`, fondo `-soft`,
tipografía 11–12 px peso 600, radio completo.

## 5. Componentes

- **Fondo general** `--tf-bg`; **listas** (columnas) en gris muy suave (`--tf-border` mezclado con
  `--tf-bg`), con nombre, contador y «⋯»; las de cierre llevan una palomita verde. **Tarjetas**
  blancas con borde de 1 px y sombra casi imperceptible; al arrastrarlas se levantan (inclinadas,
  con sombra y borde petróleo) y dejan un hueco punteado.
- **Cabecera** blanca con borde inferior. En computadora, **barra lateral navy** con el logo blanco;
  elemento activo con fondo cian claro al 18 % y barra cian claro (`--tf-accent-on-dark`) a la
  izquierda. En teléfono, navegación inferior blanca con barra petróleo sobre la pestaña activa.
- **Botones:** principal navy con texto blanco (hover `#1E3A8A`); el petróleo queda para
  indicadores (pestaña activa, barra de avance, interruptores); secundario blanco con borde;
  destructivo con borde y texto rojo. Radio 8–10 px.
- **Enfoque** (teclado y campos): contorno petróleo.
- **Sombras:** `0 1px 3px rgba(15,23,42,.06)` y, para flotantes, `0 8px 24px rgba(15,23,42,.10)`.
  Sin brillos, neón, 3D ni gradientes.
- **Animaciones** cortas (120–180 ms) y desactivadas con `prefers-reduced-motion`.
