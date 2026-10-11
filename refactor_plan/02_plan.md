# Plan de refactorización — CarTeis

Basado en [01_auditoria.md](01_auditoria.md). Stack que se mantiene: **Python 3.12 + PyQt6 + SQLite + reportlab**.

## Decisiones tomadas (2026-10-11)

| # | Tema | Decisión |
|---|---|---|
| 1 | Acceso a SQLite | `sqlite3` de la librería estándar; se deja `QtSql` |
| 2 | Excel | `.xlsx` con `openpyxl`; se eliminan `xlwt` y `xlrd` |
| 3 | Esquema | Se migra: fechas ISO `YYYY-MM-DD`, salario numérico, teléfono texto, baja `NULL` |
| 4 | Idioma | **Código en inglés**: módulos, clases, funciones, variables, tablas y columnas. Los textos que ve el usuario siguen en **español** |
| 5 | Datos en git | Son ficticios: se mantiene la BD versionada, como BD semilla |
| 6 | Binarios | Se dejan de versionar a partir de ahora, sin reescribir el historial |

## Principios

1. **La app debe arrancar y funcionar al terminar cada fase.** Nada de "big bang": se sustituye pieza a pieza.
2. **Primero la red de seguridad, después los cambios.** Antes de mover lógica, se cubre con tests.
3. **Separar en capas** con dependencias en un solo sentido: `ui → servicios → dominio ← datos`. El dominio no conoce ni Qt ni SQL.
4. **Sin estado global.** Las dependencias se crean en el arranque y se pasan por constructor.
5. **Los errores se ven.** Excepciones propias en dominio y servicios, un único punto que las muestra al usuario y `logging` en lugar de `print`.
6. **Cada fase en su propia rama y con commits pequeños**, revisables uno a uno.

## Arquitectura objetivo

```
carteis/
├── __main__.py            # arranque: python -m carteis
├── app.py                 # composición: crea BD, repositorios, servicios y ventana
├── config.py              # rutas (datos de usuario vía QStandardPaths), tarifas, IVA, versión
├── domain/                # Python puro, sin Qt ni SQL
│   ├── models.py          # dataclasses: Driver, Client, Invoice, Trip
│   ├── validators.py      # DNI/NIE, teléfono, salario (una sola implementación)
│   ├── pricing.py         # tipo de viaje → tarifa; subtotal/IVA/total con Decimal
│   └── errors.py          # ValidationError, NotFoundError, DuplicateError…
├── data/
│   ├── database.py        # conexión sqlite3, PRAGMA foreign_keys, transacciones
│   ├── migrations/        # esquema versionado + migración de los datos actuales
│   └── repositories/      # drivers, clients, invoices, locations
├── services/              # casos de uso: alta, baja, modificación, facturar,
│                          # backup, importar/exportar
├── reports/               # generación de PDF con reportlab (plantilla común)
└── ui/
    ├── generated/         # salida de pyuic6 (no se edita a mano)
    ├── main_window.py
    ├── tabs/              # un controlador por pestaña: drivers, clients, invoicing
    ├── dialogs/           # calendario, acerca de, salir
    ├── table_models.py    # QAbstractTableModel en vez de rellenar celdas a mano
    └── messages.py        # avisos y confirmaciones centralizados
resources/                 # .ui, img/, styles.qss, seed.sqlite (BD semilla)
tests/                     # pytest (+ pytest-qt para la UI)
```

Convenciones: PEP 8 en inglés (`snake_case`, `PascalCase` para clases) y type hints en todo el código nuevo. Los textos de la interfaz, los mensajes y los informes siguen en español.

## Fases

### Fase 0 — Preparación y red de seguridad ✅ (2026-10-11)
**Objetivo:** un repo limpio y reproducible, y una base para medir que no rompemos nada.

- Crear la rama `refactor`.
- Añadir `.gitignore` y **dejar de versionar** `__pycache__/`, `build/`, `dist/`, `*.exe`, `docs/_build/`, los PDFs generados y `.idea/`. Los ficheros siguen en disco; solo salen del índice.
- `pyproject.toml` con dependencias fijadas (`PyQt6`, `reportlab`, `svglib`, `openpyxl`) y herramientas: **ruff** (lint y formato) y **pytest**.
- Copia de seguridad de `bbdd.sqlite` antes de tocar nada.
- **Checklist de pruebas manuales** del comportamiento actual (alta, baja, búsqueda, facturar, informes, backup, import/export). Se repasa al final de cada fase.
- **Tests de caracterización** de la lógica pura que ya existe: validación de DNI y cálculo de tarifa.

**Criterio de salida:** `pip install -e .` deja la app funcionando, `pytest` pasa y `git status` no muestra artefactos.

### Fase 1 — Dominio ✅ (2026-10-11)
**Objetivo:** reglas de negocio en Python puro, probadas y sin duplicados.

- Dataclasses `Conductor`, `Cliente`, `Factura` y `Viaje`, que sustituyen las listas con índices mágicos.
- `validadores.py`: una única implementación de DNI/NIE, teléfono y salario. Se elimina la duplicación entre `drivers.py` y `cliente.py`.
- `tarifas.py`: tarifa según origen/destino y cálculo de subtotal, IVA y total con **`Decimal`**. Tarifas e IVA salen de `config.py`.
- Excepciones de dominio.
- Tests unitarios de todo lo anterior.

**Criterio de salida:** cobertura ≥ 90 % en `dominio/`; la app antigua sigue intacta.

**Resultado (2026-10-11) ✅** — `carteis/domain/` con `models`, `validators`, `pricing`, `formatting`, `money` y `errors`, más `carteis/config.py`. 173 tests y cobertura del 100 %. Los tests de paridad (`tests/legacy/test_parity.py`) confirman que el validador de DNI coincide con el antiguo en 2.000 casos aleatorios y que las tarifas son las mismas. Los 89 registros de la BD actual se cargan en los modelos nuevos sin errores, quitando solo el `.0` de los teléfonos importados desde Excel.

Cambios de comportamiento deliberados respecto al código antiguo:
- **Importes:** `1.500` se lee como mil quinientos (separador de miles español); el código antiguo lo leía como 1,5. Se aceptan los cuatro formatos de salario que hay en la BD.
- **Redondeo:** cada línea se redondea a céntimos y el IVA se redondea antes de sumarlo al total. El código antiguo sumaba el IVA sin redondear, así que el total puede diferir en 1 céntimo en casos raros.
- **Ruta vacía:** sin origen o destino ya no se calcula tarifa local; es un error de validación.
- **DNI con espacios** alrededor (`" 12345678Z "`): ahora se acepta, porque se recortan los espacios.
- **Validación completa:** se comprueban todos los campos obligatorios, sin el bug F10 que ignoraba el último.
- **Formato de dinero y fechas** hecho a mano, sin depender del locale `es_ES.UTF-8`.

### Fase 2 — Capa de datos ✅ (2026-10-11)
**Objetivo:** un único acceso a SQLite, con integridad y datos bien tipados.

- `database.py` con `sqlite3`: una sola conexión, `PRAGMA foreign_keys = ON` (corrige **D4**) y transacciones explícitas.
- Repositorios que devuelven dataclasses. Se arreglan **D1, D2, D3, D6 y D7** y **F1** (buscar un DNI que no existe devuelve `None` en vez de fallar).
- **Migración de esquema versionada** (`PRAGMA user_version`), aplicada sobre una copia de la BD:
  - tablas y columnas en inglés (`drivers`, `clients`, `invoices`, `trips`, `provinces`, `municipalities`);
  - fechas a ISO `YYYY-MM-DD` (se siguen mostrando como `dd/mm/YYYY`);
  - salario numérico y teléfono como texto;
  - baja como `NULL` en lugar de `''`;
  - índices en `dni`.
  - Un script migra los datos actuales sin perder registros. El resultado pasa a ser `resources/seed.sqlite`.
- Tests de repositorios contra una BD temporal.

**Criterio de salida:** los tests de repositorios pasan y la BD migrada conserva el mismo número de registros que la original.

**Resultado (2026-10-11) ✅** — `carteis/data/` con `database.py` (conexión, transacciones y traducción de errores), `converters.py`, `migrations/` (`0001_initial_schema.sql`), `repositories/` (conductores, clientes, facturas y localidades) y `legacy_import.py`. 209 tests y cobertura del 100 %. `resources/seed.sqlite` contiene los datos actuales migrados: 19 conductores, 32 clientes, 6 facturas y 31 de 32 viajes. Los totales de las 6 facturas coinciden al céntimo con el cálculo antiguo.

Decisiones tomadas durante la fase:
- **Localidad como clave foránea** (`municipality_id`) en conductores, clientes y en el origen y destino de los viajes, en lugar de texto libre. La BD garantiza que la localidad existe y pertenece a su provincia. Hay 17 nombres de municipio repetidos en varias provincias, así que `Trip` guarda `Location` (provincia + municipio) para calcular siempre bien la tarifa.
- **Correcciones de datos** en la migración (6 registros escritos a mano): `Malaga`→`Málaga`, `Gerona`→`Girona`, `Mallorca/Palma de Mallorca`→`Illes Balears/Palma`, `Bilbao/Baracaldo`→`Vizcaya/Barakaldo`, `Santander`→`Cantabria`, y se recorta el espacio de `Jaén `. También se quita el `.0` de 3 teléfonos importados desde Excel.
- **Datos perdidos:** se descarta el viaje 41 (su factura no existe, bug D4) y los 6 conductores sin fecha de alta (bug D3) se migran con la fecha vacía.
- **Dinero en céntimos enteros** (`salary_cents`, `rate_cents`): exacto y numérico.
- Las facturas referencian al cliente por DNI (`client_dni`, con `ON UPDATE CASCADE`) y al conductor por id.

> ⚠️ La app antigua sigue escribiendo en `bbdd.sqlite`. Antes de cambiar a la app nueva (fase 4) hay que **regenerar la semilla** con `python -m carteis.data.legacy_import bbdd.sqlite resources/seed.sqlite --overwrite` para no perder lo que se haya registrado entretanto.

### Fase 3 — Servicios (casos de uso) ✅ (2026-10-11)
**Objetivo:** la lógica de "qué pasa al pulsar un botón" sale de la UI.

- `ConductorService` y `ClienteService`: alta, modificación, baja/reactivación y búsqueda.
- `FacturacionService`: crear factura **junto con sus viajes en una transacción** (corrige **D5**), añadir/modificar/borrar viajes y totales.
- `BackupService`: crea el zip con la BD cerrada o mediante la API de backup de SQLite, y **restaura validando el contenido** (corrige **D8**).
- `ImportExportService`: import/export en **`.xlsx` con `openpyxl`**, con informe real de cuántos registros se insertaron y cuántos se rechazaron y por qué (corrige **F4** y **F11**).
- Tests de servicios.

**Criterio de salida:** todo el flujo de negocio se puede ejecutar y probar sin abrir ninguna ventana.

**Resultado (2026-10-11) ✅** — `carteis/services/` con `people.py` (`DriverService`, `ClientService`), `invoicing.py`, `backup.py` y `spreadsheets.py`. 258 tests y cobertura del 100 %.

Reglas de negocio y cambios de comportamiento:
- **Alta:** un alta nueva no puede llevar fecha de baja; en conductores la fecha de alta es obligatoria. Un DNI repetido da error en vez de sobrescribir (D1/D2).
- **Modificar** devuelve si hubo cambios, para que la UI muestre "No se han modificado los campos" como hasta ahora.
- **Baja** sin fecha usa la de hoy y conserva la de alta (D3). La **reactivación** es una operación explícita; antes se hacía dando de alta otra vez el mismo DNI.
- **Buscar por DNI** valida el formato y avisa si no existe (F1).
- **Facturar** exige cliente activo, conductor activo y al menos un viaje. La tarifa la calcula siempre el servicio a partir de la ruta. Al **modificar un viaje** se recalcula su tarifa; si no cambia nada, no se toca (así se conserva el precio con el que se facturó aunque la tarifa cambie después).
- **Copias de seguridad:** se hacen y restauran con la API de backup de SQLite, sin cerrar la BD. Antes de restaurar se valida el zip: un único fichero `.sqlite`/`.db` sin rutas (evita el *zip slip*), tamaño máximo, `integrity_check` y versión del esquema (D8). Las copias de la app antigua se convierten automáticamente al esquema nuevo.
- **Excel `.xlsx`:** las columnas se reconocen por cabecera (sin distinguir mayúsculas ni tildes), así que un fichero exportado se puede importar tal cual. El código antiguo exportaba 12 columnas e importaba 10 en otro orden. Cada fila rechazada se informa con su número de fila de Excel y el motivo (F4, F11). La exportación usa fechas y números reales de Excel y mantiene el teléfono como texto.

### Fase 4 — Interfaz ✅ (2026-10-11)
**Objetivo:** la UI solo muestra datos y delega en los servicios.

- Renombrar widgets en los `.ui` con nombres con significado (`txtDni_2` → `txtApellidosConductor`…) y regenerar con un script.
- Un controlador por pestaña; se elimina **`var.py`** y el atributo `Drivers.param` (el calendario devuelve la fecha a quien lo abre).
- Tablas con `QAbstractTableModel` + `QSortFilterProxyModel`: el filtro Alta/Baja/Todos, el resaltado de la fila y la ordenación salen gratis, y desaparecen los 4 bucles de colores.
- `mensajes.py` centraliza los avisos; se corrigen erratas y **F2, F3, F5, F7, F8, F9 y F12**.
- Un manejador global de excepciones (`sys.excepthook`) muestra el error y lo registra en un log, en lugar de los 92 `print`.
- Cargar `styles.qss` (o eliminarlo, si se prefiere el estilo actual del `.ui`).
- Tests de humo de la UI con pytest-qt.

**Criterio de salida:** ~~se borran `conexion.py`, `drivers.py`, `cliente.py`, `eventos.py`, `var.py`, `windowaux.py`, `Ventanas.py` y `Facturas/`~~ (pasa a la fase 5, ver abajo); el checklist manual pasa completo.

**Resultado (2026-10-11) ✅** — `python -m carteis` arranca la app nueva. 325 tests y cobertura del 100 % (sin contar el código generado).
- **`.ui` → `resources/ui/`** con nombres en inglés (`txtDni_2` → `txtDriverSurname`, `tabDriver2` → `tblDrivers`…). `tools/build_ui.py` genera `carteis/ui/generated/` y convierte las rutas de imagen en `img:`, que funciona desde cualquier carpeta.
- **Estilo en `resources/styles.qss`:** los 102 bloques incrustados (17 estilos distintos) pasan a una propiedad dinámica `role` por grupo de widgets. Se comprobó renderizando la ventana antigua y la nueva: las tres pestañas y el diálogo de salir salen **idénticos píxel a píxel**, y "Acerca de" solo difiere en el suavizado del texto.
- **Arranque (`app.py`, `paths.py`):** la BD vive en la carpeta de datos del usuario (`%APPDATA%/CarTeis/CarTeis/carteis.sqlite`) y se crea a partir de `seed.sqlite` la primera vez; con la variable `CARTEIS_DB` se usa otro fichero. Hay un log rotativo y un `sys.excepthook` que registra el error y avisa al usuario, en lugar de los `print`.
- **Interfaz (`carteis/ui/`):** un controlador por pestaña, sin `var.py`. Modelos de tabla (`QTableView` + `RecordTableModel`) en lugar de celdas rellenadas a mano. El decorador `user_action` muestra los errores de dominio y pone el foco en el campo culpable, y todas las ventanas modales pasan por `Prompts`, que los tests sustituyen.
- **Bugs corregidos:** F2/F3 (diálogos y argumentos), F5, F7, F8, F9, F12 y las erratas visibles ("Destitno", "Restarurar Copia", "RazonSocial", el botón con el texto "btn_menu_print"…).

Cambios de comportamiento en la interfaz:
- **Reactivar:** el botón "Baja" pasa a "Reactivar" cuando el registro seleccionado está de baja. Antes se reactivaba dando de alta otra vez el mismo DNI.
- **Validación al guardar**, no al salir de cada campo: ya no salta un aviso ni se borra el campo al salir de un teléfono o DNI incorrectos. El DNI sigue mostrando el icono ✔/✘ mientras se escribe.
- **Salir:** la X de la ventana y el menú "Salir" usan el mismo diálogo de confirmación.
- **Selector de conductor en facturación:** muestra todos los conductores, con "(baja)" junto a los inactivos, para que las facturas antiguas los enseñen. Solo se puede facturar con conductores activos.
- **Lupa del cliente en facturación:** filtra la tabla de facturas por ese cliente. Antes cargaba el cliente en la pestaña de clientes. "Limpiar" quita el filtro.
- **Radio de tarifa:** solo informa; lo marca la app según la ruta y no se puede pulsar.
- **Informes PDF deshabilitados** hasta la fase 5. Mientras tanto, la app antigua (`python main.py`) sigue disponible.

> **Cambio de orden:** los informes antiguos (`informes.py`, `Facturas/facturacion_informes.py`) dependen de la BD y los globales antiguos. Borrar el código antiguo en esta fase dejaría la app sin informes hasta la fase 5, así que el borrado pasa al final de la fase 5.

### Fase 5 — Informes ✅ (2026-10-11)
**Objetivo:** PDFs generados a partir de los datos, sin estado global.

- Una plantilla común (cabecera, pie y paginación) y un generador por informe que recibe los datos y la ruta de salida; desaparece `var.report`.
- La factura usa los mismos cálculos (`Decimal`) que la pantalla.
- Salida en la carpeta de documentos del usuario y apertura multiplataforma (`QDesktopServices.openUrl`).

- **Retirada de la app antigua** (movida desde la fase 4): regenerar `resources/seed.sqlite` desde `bbdd.sqlite`; borrar `main.py`, `conexion.py`, `drivers.py`, `cliente.py`, `eventos.py`, `informes.py`, `var.py`, `windowaux.py`, `Ventanas.py`, `Facturas/`, los módulos generados antiguos (`MainWindow.py`…), `tests/legacy/` y las dependencias `xlrd`/`xlwt`; mover `img/` a `resources/img/`.

**Criterio de salida:** los tres informes se generan con el mismo contenido que hoy y tienen tests que comprueban que el PDF se crea; ya no queda código antiguo y el checklist manual pasa completo con la app nueva.

**Resultado (2026-10-11) ✅** — 285 tests y cobertura del 100 %; ruff pasa sobre todo el repositorio, que antes daba 411 avisos.
- **`carteis/reports/`:** `pdf.py` tiene la plantilla común (cabecera de empresa con logo, pie con fecha, título y página) y una `Table` que repite su cabecera en cada página y recorta con "…" el texto que no cabe. `documents.py` genera el listado de conductores, el de clientes (con el DNI enmascarado) y la factura. Los datos de la empresa están en `config.COMPANY`.
- **`ReportService`** guarda los PDFs en `Documentos/CarTeis/Informes` y `Documentos/CarTeis/Facturas` con los nombres de siempre, y la interfaz los abre con el visor del sistema (`QDesktopServices`), no con `os.startfile`, que solo funciona en Windows.
- **Comparación con la app antigua:** generado con los datos actuales, el listado de clientes coincide fila por fila con el que produjo la app antigua en febrero de 2024. Solo cambian las localidades corregidas en la migración y las erratas. La factura 1 da los mismos totales (57,60 / 12,10 / 69,70 €).
- **Cambios en los informes:** errata "Trasnsportes Teis" corregida; la factura incluye el **DNI/CIF del cliente**; los totales pasan a la página siguiente si no caben, en vez de pisar el pie; una factura sin viajes muestra los totales a 0; el botón de imprimir de la barra genera el listado que se marca (F2) y avisa si no se marca ninguno (F3).
- **Retirada de la app antigua:** borrados los módulos antiguos, sus tests de caracterización, `bbdd.sqbpro` y las dependencias `xlrd`, `xlwt` y `svglib` (esta última se importaba pero no se usaba). `img/` pasa a `resources/img/`. `bbdd.sqlite` pasa a `tests/fixtures/legacy_bbdd.sqlite`, y con ella se prueba que se pueden convertir y restaurar copias reales de la versión antigua. Antes de borrar se comprobó que `seed.sqlite` es idéntica a una conversión nueva de `bbdd.sqlite`.
- Los PDFs generados en su día por la app antigua siguen en `informes/` y `Facturacion/` (en disco, sin versionar).
- **Pendiente para la fase 6:** `main.spec` (PyInstaller) y `docs/` (Sphinx) aún apuntan a los módulos antiguos.

### Fase 6 — Empaquetado, documentación y cierre
- Rutas: los recursos se leen relativos al paquete y la BD vive en la carpeta de datos del usuario (`QStandardPaths`); la primera vez se copia la BD inicial.
- Arreglar `main.spec` para que el `.exe` use esa BD persistente.
- Sphinx con rutas relativas; actualizar `README.md` y `CLAUDE.md`.
- Pasada final de ruff, revisión de código y checklist manual completo.

**Criterio de salida:** el `.exe` arranca en una carpeta cualquiera y conserva los datos entre ejecuciones.

## Orden y dependencias

```
F0 ──► F1 ──► F2 ──► F3 ──► F4 ──► F5 ──► F6
             (dominio y datos se pueden solapar)
```

Durante F1–F3 el código nuevo convive con el antiguo sin que la UI lo use. En F4 se conecta la UI al código nuevo y se borra el antiguo. Así el riesgo se concentra en una sola fase, que ya llega con tests detrás.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| La migración de datos pierde o corrompe registros | Siempre sobre una copia, con script reversible y verificación de conteos |
| Renombrar widgets rompe referencias | Un solo commit por `.ui`, con búsqueda automática de referencias antiguas |
| Cambios de comportamiento no deseados | Checklist manual y tests de caracterización desde F0 |
| Alcance que crece | Las funcionalidades nuevas quedan fuera; solo se corrige y reestructura |

