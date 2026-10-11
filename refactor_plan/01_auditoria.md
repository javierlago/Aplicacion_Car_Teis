# Auditoría de calidad — CarTeis

Fecha: 2026-10-11 · Alcance: todo el código propio (≈3.700 líneas). Se excluyen los módulos generados por `pyuic6` (`MainWindow.py`, `AcercaDeWindow.py`, `VentanaSalir.py`, `WindowCalendar.py`).

Stack que se mantiene: **Python + PyQt6 + SQLite + reportlab**.

---

## 1. Resumen

La app funciona en el camino feliz, pero:

- **No hay arquitectura por capas.** UI, lógica de negocio y SQL están mezclados en las mismas funciones.
- **Todo depende de un estado global** (`var.ui`): ningún módulo se puede probar ni reutilizar sin la ventana principal.
- **Los errores se silencian.** Hay 92 bloques `except Exception` que solo hacen `print`, así que los fallos no llegan al usuario.
- **Hay bugs reales de datos**: duplicados, pérdida de fechas, borrados en cascada que no se aplican y cálculos monetarios con `float`.
- **El repositorio está sucio**: 134 ficheros generados (`.pyc`, `build/`, `dist/`, `.exe`, PDFs) versionados, sin `.gitignore` ni lista de dependencias.

| Área | Estado | Gravedad |
|---|---|---|
| Arquitectura | Sin capas, estado global, imports circulares | Alta |
| Integridad de datos | Varios bugs que corrompen o pierden datos | Alta |
| Gestión de errores | Silenciada en casi todo el código | Alta |
| Duplicación | Validadores, carga de tablas y resaltado de filas copiados | Media |
| Modelo de datos | Fechas y dinero como texto, tipos incorrectos | Media |
| Tests | Inexistentes | Alta |
| Portabilidad y empaquetado | Rutas Windows relativas al directorio de trabajo, spec de PyInstaller incoherente | Media |
| Higiene del repo | Artefactos versionados, sin dependencias declaradas | Media |

---

## 2. Arquitectura

### 2.1 Estado global en `var.py`
`var.ui`, `var.calendar`, `var.report`, `var.bbdd`… son variables de módulo que todos leen y escriben. Consecuencias:
- Cualquier función depende implícitamente de que la ventana exista; no se puede probar la lógica sin arrancar Qt.
- `var.report` (el canvas de reportlab) es compartido: dos informes no pueden convivir.
- `drivers.Drivers.param` es un atributo de clase usado como "a qué campo va la fecha del calendario" ([drivers.py:253-274](../drivers.py#L253-L274)).

### 2.2 Sin separación de capas
Un mismo método lee widgets, valida, ejecuta SQL y muestra diálogos. Ejemplos:
- `Conexion.modificar` ([conexion.py:216](../conexion.py#L216)): consulta a la BD, valida, actualiza y construye un `QMessageBox` a mano.
- `Facturacion.mostrar_datos_factura` ([facturacion.py:94](../Facturas/facturacion.py#L94)): lanza SQL directamente desde la capa de UI.
- `conexion.py` es un "cajón de sastre": conexión, conductores, clientes, provincias y facturas en una sola clase.

### 2.3 Clases usadas como espacios de nombres
Los métodos se declaran sin `self` ni `@staticmethod` y se llaman sobre la clase (`drivers.Drivers.alta_driver`). Hay firmas incoherentes (`self`, `self=None`, `registro` en primera posición) y algunas se llaman pasando un `self` falso (`Facturacion.rellenar_tabla_lineas_viaje(self=None)`).

### 2.4 Imports circulares
`conexion` ↔ `cliente` ↔ `drivers` ↔ `eventos` ↔ `Facturas.*` se importan entre sí. Además, cada módulo se importa a sí mismo (`import drivers` dentro de `drivers.py`), y hay imports peligrosos: `from PyQt6 import *`, `from Facturas import *`, y `from PyQt6.uic.properties import QtWidgets, QtCore, QtGui` (un módulo interno de uic) que luego se sobrescribe.

### 2.5 Registros como listas con índices mágicos
Los datos viajan como listas: `registro[11]` es la fecha de baja del conductor, `registro[7]` la del cliente, y `driver.pop(0)` o `driver[:2] + driver[3:]` reajustan posiciones. Un cambio de columna rompe silenciosamente media app.

### 2.6 UI
- Una sola ventana de 2.172 líneas generadas.
- Nombres de widgets sin significado: `txtDni_2` son los apellidos, `txtDni_3` es el DNI del cliente y `tabDriver2` es la tabla.
- `styles/styles.qss` existe pero no se carga (el estilo está incrustado en el `.ui`).
- Todo el cableado de señales está en `main.py`, con conexiones duplicadas (`tab_facturas.clicked` → `rellenar_tabla_lineas_viaje` dos veces, [main.py:166-167](../main.py#L166-L167)).

---

## 3. Bugs detectados

### 3.1 Integridad de datos (críticos)

| # | Ubicación | Problema | Efecto |
|---|---|---|---|
| D1 | [conexion.py:181-184](../conexion.py#L181-L184) `guardardri` | `query2` se prepara pero **nunca se ejecuta**, así que `query2.next()` es siempre `False` | La comprobación de "ya existe" no funciona; la importación XLS no detecta duplicados |
| D2 | [conexion.py:188-189](../conexion.py#L188-L189) | Si el conductor tiene fecha de baja, el `else` la borra (`newdriver[10] = ''`) y hace un UPDATE | Dar de alta con fecha de baja reactiva y sobrescribe a otro conductor |
| D3 | [conexion.py:427-430](../conexion.py#L427-L430) `borrarDriver` | Al dar de baja se pone `altadri = ''` | **Se pierde la fecha de alta** del conductor |
| D4 | Esquema + [conexion.py:85](../conexion.py#L85) | `viajes` tiene `ON DELETE CASCADE`, pero nunca se ejecuta `PRAGMA foreign_keys = ON` | Al borrar una factura sus viajes quedan **huérfanos** |
| D5 | [facturacion_repository.py:107-115](../Facturas/facturacion_repository.py#L107-L115) `insert_factura` | No comprueba el resultado del INSERT y no usa transacción; si falla el viaje, la factura queda creada sin líneas | Facturas vacías o inconsistentes |
| D6 | [conexion.py:505-519](../conexion.py#L505-L519) `guardarCliente` | Lógica invertida: si existe y está de baja, lo reactiva sin guardar los demás datos; si no, intenta un INSERT que falla por `UNIQUE` | Comportamiento confuso al dar de alta |
| D7 | [facturacion_repository.py:179-180](../Facturas/facturacion_repository.py#L179-L180), [193-194](../Facturas/facturacion_repository.py#L193-L194) | `exec()` llamado **dos veces** en los DELETE | Inocuo hoy, pero es un error de lógica |
| D8 | [eventos.py:219-220](../eventos.py#L219-L220) `restaurar_back_up` | Extrae el zip sobre el directorio actual **con la BD abierta** y sin validar el contenido (riesgo de *zip slip*) | Restauración no fiable, posible sobrescritura de ficheros arbitrarios |

### 3.2 Funcionales

| # | Ubicación | Problema |
|---|---|---|
| F1 | [conexion.py:371](../conexion.py#L371), [397](../conexion.py#L397) | `registro[11]` sobre una lista vacía si el DNI no existe → `IndexError`, la función devuelve `None` y el llamador vuelve a fallar. Es el error que vimos al ejecutar la app |
| F2 | [eventos.py:542-547](../eventos.py#L542-L547) `printear_informes` | Casillas **intercambiadas**: marcar "conductores" genera el de clientes y viceversa |
| F3 | [eventos.py:550](../eventos.py#L550), [171](../eventos.py#L171), [205](../eventos.py#L205), [226](../eventos.py#L226), [250](../eventos.py#L250) | `ventana_info` y `mensaje_warning` se llaman con 2 argumentos y solo aceptan 1 → `TypeError` dentro del propio `except` |
| F4 | [eventos.py:167](../eventos.py#L167), [201](../eventos.py#L201) | "Se ha exportado correctamente" aparece aunque el usuario cancele |
| F5 | [drivers.py:135](../drivers.py#L135) | `Ventanas.mensaje_warning` (módulo, no clase) → `AttributeError` |
| F6 | [drivers.py:170](../drivers.py#L170), [cliente.py:262](../cliente.py#L262) | Compara un `QTableWidgetItem` con un `str`: nunca es cierto, así que el bloque (que además tiene llamadas a `setItem` mal formadas) es código muerto |
| F7 | [cliente.py:257](../cliente.py#L257) | Al cargar un cliente se actualiza el icono de DNI del **conductor** (`lblCheckDNI`) |
| F8 | [cliente.py:59](../cliente.py#L59) | `alta_cliente` refresca la tabla de conductores |
| F9 | [conexion.py:593-597](../conexion.py#L593-L597) `cargar_facturas` | Rellena la tabla **dentro del bucle** (O(n²)) y, si no hay facturas, no la vacía |
| F10 | [drivers.py:362](../drivers.py#L362) / [cliente.py:72](../cliente.py#L72) `validar_datos` | Ignora siempre el último elemento (`len - 1`) sin documentarlo; se reutiliza para facturas y viajes, donde ese último campo sí importa |
| F11 | [eventos.py:121-128](../eventos.py#L121-L128) `importar_datos` | Dice "Empleados dados de alta" aunque no se inserte ninguno |
| F12 | [main.py:173-182](../main.py#L173-L182) `closeEvent` | Usa la variable global `app` del bloque `__main__` |

### 3.3 Cálculos y formatos

- **Dinero en `float`**: tarifas (0.2/0.4/0.8), IVA 21 % y totales con `float` y `round` ([facturacion.py:249-254](../Facturas/facturacion.py#L249-L254)). Hay que usar `Decimal`.
- **Totales recalculados leyendo la tabla visual** (`tabla.item(a, 5).text()`), no los datos.
- **Tarifas e IVA en el código**: no son configurables y están duplicados entre pantalla e informe.
- **Salario guardado como texto con formato de moneda** ("1.234,00 €") tras `locale.currency` ([drivers.py:245](../drivers.py#L245)).
- **Fechas como texto `dd/mm/YYYY`**: no se pueden ordenar ni filtrar en SQL.
- **Teléfono `NUMERIC`** en `listadoClientes`: puede perder ceros a la izquierda o formato.
- **Bajas detectadas con `== ''`**, mezclando `''` y `NULL` (`bajacliente IS ''`).

---

## 4. Calidad del código

| Problema | Datos |
|---|---|
| Errores silenciados | 92 `except Exception` → `print` |
| Depuración en producción | 124 `print(...)` |
| Duplicación | `validar_dni` (×2, 50 líneas), `validar_tlf` (×2), `validar_datos` (×2), `cargartabla` (×3), resaltado de filas (×4), limpiar paneles (×4) |
| Literales repetidos | Color de resaltado `QColor(243, 220, 173)` ×8, separador `"  ||  "`, rutas de iconos |
| Mensajes | Erratas al usuario ("icorrecto", "Fatura", "Campos vaios", "empeado") y mensajes incoherentes con lo que ocurre |
| Docstrings | Abundantes pero a menudo **incorrectos** (`buscar_segun_dni_cliente` dice "conductor"; `rellenar_tabla_lineas_viaje` documenta otro método) |
| Nombres | Mezcla de estilos (`borrarDriver`, `get_from_dni`, `Facturacion_Repository`, `comprobarr_factura_existe`) y de idiomas (driver/conductor) |
| Código comentado | Restos en `drivers.py`, `eventos.py` e `informes.py` |
| Locale | `setlocale('es_ES.UTF-8')` repetido en dos módulos; si no existe, la app no arranca |

---

## 5. Seguridad

- Las consultas usan `bindValue` (no hay inyección SQL). 👍
- Restauración de backup sin validar el zip (ver D8).
- Datos personales (DNI, teléfonos) en `bbdd.sqlite` **versionados en git**. *Revisado: según el autor, todos los datos son ficticios, así que se mantiene versionada.*
- El informe de clientes enmascara el DNI (`XXXXXX` + últimos dígitos), pero la exportación XLS no.

---

## 6. Repositorio, build y documentación

- Versionados sin necesidad: `__pycache__/`, `build/`, `dist/main.exe`, `Instalador.exe`, `docs/_build/`, PDFs generados, `.idea/` (134 ficheros; `.git` ocupa 99 MB).
- Sin `requirements.txt` ni `pyproject.toml`, sin linter ni formateador.
- **Sin tests.**
- `main.spec` mete `bbdd.sqlite` dentro del `.exe` *onefile*, pero el código abre `bbdd.sqlite` relativo al directorio actual: el empaquetado es incoherente y los datos no persisten de forma fiable.
- Rutas con `\\` y `os.startfile`: solo funciona en Windows y solo si se arranca desde la raíz del proyecto.
- `docs/conf.py` apunta a una ruta absoluta de otro equipo.
- `xlwt` está abandonado y solo escribe `.xls`; `xlrd` 2.x solo lee `.xls`.
