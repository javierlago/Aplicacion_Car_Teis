# Fase 7 — Rediseño visual ✅

Continuación de [02_plan.md](02_plan.md). El objetivo es una interfaz **clara y moderna**, con el amarillo taxi como acento, que se vea igual en cualquier equipo.

## Decisiones tomadas (2026-10-11)

| Tema | Decisión |
|---|---|
| Dirección visual | Claro moderno: fondos blancos y gris muy claro, texto oscuro, amarillo taxi solo como acento |
| Alcance | Estilo **y** distribución: se reorganizan los formularios en los `.ui` |
| Iconos | Un set SVG único y de licencia libre en lugar de los PNG actuales |

## Problemas de partida

- **Fuentes no garantizadas:** la interfaz usa `Alef` (no viene con Windows) y `Montserrat ExtraBold` (no instalada; se sustituye por Tahoma). En otro equipo la app se ve distinta.
- **Colores atados al tema de Windows:** parte del aspecto sale de la paleta del sistema, así que en modo claro y en modo oscuro la app es muy diferente.
- **114 fuentes fijadas en el `.ui`**, que pisan lo que dice el `.qss`.
- **Distribución con posiciones casi fijas:** grandes huecos en los formularios, botones pequeños y alineaciones irregulares.
- **Iconos de estilos y tamaños distintos.**

## Principios

1. **Mismo aspecto en cualquier equipo:** estilo `Fusion` de Qt con una paleta propia, sin depender del tema de Windows, y la fuente incluida en la app.
2. **Los nombres de los widgets no cambian:** los controladores y los 287 tests siguen funcionando sin tocarse. Si un test falla, es una regresión.
3. **Una sola fuente de verdad para el diseño:** colores, tamaños y espaciados definidos una vez como *tokens*.
4. **Cada paso se valida con capturas** antes de seguir.

## Propuesta de diseño

| Token | Valor | Uso |
|---|---|---|
| `background` | `#F4F5F7` | Fondo de la ventana |
| `surface` | `#FFFFFF` | Tarjetas, campos y tablas |
| `border` | `#DDE1E6` | Bordes de campos y tarjetas |
| `text` | `#1F2328` | Texto principal |
| `muted` | `#5F6B7A` | Etiquetas secundarias y texto de ayuda |
| `accent` | `#F7B500` | Amarillo taxi: botón principal, fila seleccionada, pestaña activa |
| `accent-hover` | `#E0A400` | Hover y pulsado del botón principal |
| `danger` | `#C62828` | Acciones de baja y borrado |
| `success` | `#2E7D32` | Validaciones correctas (DNI ✔) |

- **Tipografía:** **Inter** (licencia SIL OFL, se incluye en la app). 10 pt de base, 13 pt para los títulos de sección y semibold en las etiquetas de tabla.
- **Formas:** bordes redondeados de 6 px y espaciado en múltiplos de 4/8 px.
- **Contraste:** el amarillo nunca se usa para texto sobre blanco, porque no da contraste suficiente. Se usa como fondo con texto oscuro (ratio ≈ 10:1). Todos los pares texto/fondo cumplirán WCAG AA y se comprobarán con un script.
- **Iconos:** **Lucide** (licencia ISC), trazo uniforme de 2 px y en color `text`. Se mantienen el logo del taxi y el icono de la app, que son la imagen de marca.

### Distribución

- **Conductores y Clientes:**
  - el formulario va en una tarjeta con rejilla de dos columnas y etiquetas alineadas;
  - los botones van abajo a la derecha, del mismo tamaño: **Alta** (principal, amarillo), **Modificar** (secundario) y **Baja/Reactivar** (peligro, en rojo con contorno);
  - el filtro Todos/Alta/Baja se coloca junto a la tabla como control segmentado;
  - la tabla ocupa el espacio restante.
- **Facturación:**
  - arriba, dos tarjetas lado a lado: *Factura* (número, cliente, conductor, fecha) y *Viaje* (origen, destino, km, tarifa);
  - debajo, la tabla de facturas a la izquierda y la de viajes a la derecha;
  - los totales van en una tarjeta resumen alineada a la derecha.
- **Barra de herramientas:** iconos nuevos con tooltip, agrupados (informes · copias · limpiar · salir).
- **Diálogos** (Acerca de, Salir, Calendario, Elegir informes): mismo lenguaje visual.

## Pasos

### 7.1 — Base técnica y prototipo de estilo
- Incluir la fuente Inter (`resources/fonts/` + licencia) y cargarla al arrancar.
- `Fusion` con una paleta clara propia; los colores del `.qss` salen de los tokens (`carteis/ui/theme.py` sustituye `@token` en `styles.qss`).
- Quitar las 114 fuentes fijas de los `.ui`.
- Nuevo `styles.qss` aplicado sobre la distribución actual.
- **Entregable:** capturas de las tres pestañas para que valides colores y tipografía antes de mover nada.

### 7.2 — Distribución
- Rehacer los cuatro `.ui` con layouts de Qt (rejillas y cajas) en lugar de posiciones casi fijas, manteniendo todos los nombres de objeto.
- Tamaño mínimo de ventana de 1280×720 y comportamiento correcto al redimensionar.
- **Entregable:** capturas antes/después de cada pestaña y diálogo.

### 7.3 — Iconos
- Descargar los SVG de Lucide necesarios (buscar, calendario, papelera, imprimir, copia, restaurar, limpiar, salir, ✔/✘) a `resources/img/icons/` con su licencia, recoloreados con el token `text`.
- Sustituir los PNG en los `.ui` y en el código; borrar los PNG que queden sin uso.

### 7.4 — Cierre
- Tests de interfaz, cobertura del 100 % y test de imágenes existentes en verde.
- Script de contraste de la paleta (WCAG AA).
- Capturas finales en `docs/img/` y en el README; actualizar `docs/` y CLAUDE.md (cómo usar los tokens y `role`).
- Pasada por la lista de pruebas manuales.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Al rehacer un `.ui` se pierde o renombra un widget | Script que compara los nombres de objeto antes y después; los tests de interfaz los usan todos |
| El amarillo no se lee bien sobre blanco | Solo como fondo con texto oscuro; script de contraste |
| Cambios que no gusten | Prototipo con capturas en 7.1 antes de tocar la distribución |
| Licencias de fuente e iconos | Inter (OFL) y Lucide (ISC) permiten incluirlos; los ficheros de licencia van junto a ellos |

## Resultado (2026-10-11)

**7.1 ✅ Base técnica y estilo.** Fuente Inter incluida, estilo Fusion con paleta propia y colores como tokens (`carteis/ui/theme.py` → `@token` en `styles.qss`). Se quitaron las 39 fuentes fijas de los `.ui` y Modificar, Baja y los botones de icono tienen su propio rol. Por los comentarios del autor se oscureció el fondo (`#E6E9ED`) y se sustituyó el marco nativo de los desplegables, que dibujaba una esquina negra, por una flecha de Lucide.

**7.2 ✅ Distribución.**
- Los tres formularios son rejillas: la etiqueta y su campo comparten fila, así que quedan centrados entre sí. Antes, etiquetas y campos estaban en columnas separadas que se desplazaban entre ellas.
- Etiquetas y campos se alinean a la izquierda, y todas las filas tienen 28 px de altura mínima, de modo que las tarjetas de Factura y Viaje coinciden fila a fila.
- Cada pestaña tiene un único ancho de contenido (máximo 1160 px) para la tarjeta y las tablas. Sus bordes coinciden al píxel a 1280×720 y 1600×950, y un test lo comprueba.
- Las tablas alinean cada columna según su contenido: texto a la izquierda, importes a la derecha y códigos centrados.
- Diálogos:
  - el de salir tenía botones recortados (ancho mínimo de 75 px y máximo de 60 px) y textos con erratas; ahora tiene los botones centrados;
  - "Acerca de" mostraba otro proyecto ("TappxiControl 0.0.0.0");
  - el calendario sale en español y sin números de semana.

**7.3 ✅ Iconos.** Los iconos de la barra de herramientas, los menús, los botones del formulario, las papeleras de las tablas y la marca del DNI son ahora SVG de Lucide (`tools/fetch_icons.py`), coloreados con los tokens del tema: oscuros en la barra, grises en los formularios y verde/rojo para el DNI válido o no válido. Todos los botones de icono usan el mismo tamaño (18 px, desde `styles.qss`); antes el calendario medía 24 px y la lupa 16 px. Se borraron los 10 PNG/ICO antiguos y se conservaron solo las imágenes de marca (el taxi, el icono de la ventana y del `.exe` y el logo de los PDF). Capturas en `refactor_plan/capturas/7.3_*`.

**7.4 ✅ Cierre.** 299 tests, cobertura del 100 %, documentación (`docs/`, CLAUDE.md) y README con capturas nuevas (`docs/img/`). Las capturas de cada paso están en `refactor_plan/capturas/`.
