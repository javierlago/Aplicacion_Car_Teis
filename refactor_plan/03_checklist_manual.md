# Checklist de pruebas manuales

Se repasa **al final de cada fase**. Hay que trabajar sobre una copia de la BD:

```sh
cp backups/bbdd_2026-10-11_pre-refactor.sqlite bbdd.sqlite   # partir de la BD original
.venv/Scripts/python main.py
git checkout bbdd.sqlite                                     # descartar los cambios al terminar
```

Cada caso tiene la columna **Hoy** con el comportamiento de la versión original (2026-10-11). Los casos marcados ❌ son bugs conocidos: después del refactor deben comportarse como indica **Esperado**.

Para la app nueva: `python -m carteis` (con `CARTEIS_DB=<copia>.sqlite` para no tocar los datos reales). La columna **App nueva** indica el estado tras la fase 4; casi todos los casos están cubiertos también por los tests de `tests/ui/`.

> La columna **Hoy** se ha rellenado **leyendo el código**, no probando la app a mano (salvo A1, A2 y C13, que se vieron al ejecutarla). El autor la acepta como referencia sin verificarla a mano (2026-10-11).

## Datos de referencia (BD original)

| Tabla | Registros | Notas |
|---|---|---|
| provincias | 52 | |
| municipios | 8116 | |
| drivers | 19 | 6 de baja, y esos 6 **sin fecha de alta** (bug D3) |
| listadoClientes | 32 | 9 de baja |
| facturas | 6 | |
| viajes | 32 | 1 huérfano, de una factura borrada (bug D4) |

## Arranque

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| A1 | Arrancar la app | Ventana maximizada, tablas de conductores, clientes y facturas cargadas | ✅ | ✅ |
| A2 | Barra de estado | Fecha de hoy y versión | ✅ | ✅ |
| A3 | Cerrar con la X → "No" | La app sigue abierta | ✅ | ✅ |
| A4 | Archivo → Salir → Aceptar | La app se cierra | ✅ | ✅ |

## Conductores

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| C1 | Filtros Alta / Baja / Todos | La tabla muestra solo los que corresponden | ✅ | ✅ |
| C2 | Clic en una fila | Se cargan sus datos en el formulario y la fila se resalta | ✅ | ✅ |
| C3 | DNI inválido (`12345678A`) al salir del campo | Icono rojo y campo vacío | ✅ | ✅ (solo icono ✘; ya no borra el campo) |
| C4 | Móvil con menos de 9 dígitos | Aviso y campo vacío | ✅ | ✅ (aviso al guardar) |
| C5 | Salario `1500,5` | Se formatea como `1.500,50 €` | ✅ | ✅ |
| C6 | Alta completa con DNI nuevo | "Empleado dado de alta" y aparece en la tabla | ✅ | ✅ |
| C7 | Alta con campos vacíos | Aviso "Campos vacíos" | ✅ | ✅ |
| C8 | Alta con DNI ya existente | Aviso de duplicado y **no** modifica al existente | ❌ D1/D2 | ✅ corregido |
| C9 | Modificar un dato y pulsar Modificar | "Se ha modificado" y la tabla se actualiza | ✅ | ✅ |
| C10 | Modificar sin cambiar nada | Aviso "No se han modificado los campos" | ✅ | ✅ |
| C11 | Baja de un conductor activo | Pasa a la lista de bajas **conservando la fecha de alta** | ❌ D3 | ✅ corregido |
| C12 | Buscar (lupa) un DNI existente | Carga sus datos y resalta su fila | ✅ | ✅ |
| C13 | Buscar un DNI que **no** existe | Aviso "DNI no encontrado" | ❌ F1 (no hace nada) | ✅ corregido |
| C14 | Botón calendario de alta / baja | Elige la fecha y la escribe en el campo correcto | ✅ | ✅ |

## Clientes

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| L1 | Filtros Alta / Baja / Todos | La tabla muestra solo los que corresponden | ✅ | ✅ |
| L2 | Clic en una fila | Se cargan sus datos | ✅ | ✅ |
| L3 | Alta completa con DNI nuevo | "Cliente dado de alta" | ✅ | ✅ |
| L4 | Alta con DNI ya existente | Aviso de duplicado | ✅ | ✅ |
| L5 | Modificar cliente | "Modificación realizada" | ✅ | ✅ |
| L6 | Baja de un cliente activo | Pasa a la lista de bajas | ✅ | ✅ |
| L7 | Baja de un cliente ya de baja | Aviso "ya está dado de baja" | ✅ | ✅ (el botón pasa a «Reactivar») |
| L8 | Buscar un DNI que **no** existe | Aviso "DNI no encontrado" | ❌ F1 | ✅ corregido |
| L9 | El icono de DNI válido aparece en la pestaña de clientes | Icono junto al DNI del cliente | ❌ F7 (aparece en conductores) | ✅ corregido |

## Facturación

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| T1 | Clic en una factura | Carga cliente, fecha, conductor y sus viajes, con subtotal, IVA (21 %) y total | ✅ | ✅ |
| T2 | Tarifa: mismo municipio / misma provincia / otra provincia | 0,20 / 0,40 / 0,80 €/km | ✅ | ✅ |
| T3 | Facturar con cliente, fecha, conductor y un viaje | Se crea la factura **con su viaje** | ✅ | ✅ |
| T4 | Facturar con cliente inexistente / de baja | Aviso y no se crea nada | ✅ | ✅ |
| T5 | Añadir viaje a una factura existente | Aparece en la tabla y se recalculan los totales | ✅ | ✅ |
| T6 | Seleccionar un viaje, cambiarlo y pulsar Modificar | Se actualiza y se recalcula la tarifa | ✅ | ✅ |
| T7 | Borrar un viaje (papelera) | Pide confirmación y desaparece | ✅ | ✅ |
| T8 | Borrar una factura (papelera) | Pide confirmación y desaparecen **la factura y sus viajes** | ❌ D4 (los viajes quedan) | ✅ corregido |

## Informes

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| I1 | Informes → Listar clientes | PDF de clientes con el DNI enmascarado, se abre solo | ✅ | ⏳ fase 5 |
| I2 | Informes → Listar conductores | PDF de conductores, se abre solo | ✅ | ⏳ fase 5 |
| I3 | Imprimir (barra) → marcar solo "conductores" | Genera el informe **de conductores** | ❌ F2 (genera el de clientes) | ⏳ fase 5 |
| I4 | Imprimir sin marcar nada | Aviso "No se ha seleccionado ningún informe" | ❌ F3 (falla en silencio) | ⏳ fase 5 |
| I5 | Imprimir factura con una factura seleccionada | PDF con los datos del cliente, viajes y totales | ✅ | ⏳ fase 5 |
| I6 | Imprimir factura sin seleccionar ninguna | Aviso "Selecciona una factura" | ✅ | ⏳ fase 5 |

## Herramientas

| # | Caso | Esperado | Hoy | App nueva (fase 4) |
|---|---|---|---|---|
| H1 | Crear copia de seguridad | Se guarda un `.zip` con la BD en la ruta elegida | ✅ | ✅ |
| H2 | Restaurar copia | Se recupera la BD y se refrescan **todas** las tablas | ❌ D8 (BD abierta, solo refresca conductores) | ✅ corregido |
| H3 | Exportar conductores / clientes a Excel | Fichero con todos los registros | ✅ (`.xls`; `.xlsx` desde la fase 3) | ✅ (`.xlsx`) |
| H4 | Exportar y **cancelar** el diálogo | No aparece ningún mensaje de éxito | ❌ F4 | ✅ corregido |
| H5 | Importar conductores desde Excel con un DNI duplicado | Informa de cuántos se insertaron y cuántos se rechazaron | ❌ D1/F11 | ✅ corregido |
| H6 | Importar clientes desde Excel | Informa de los añadidos, duplicados y DNIs mal formados | ✅ | ✅ |
| H7 | Limpiar (barra) | Vacía todos los formularios | ✅ | ✅ |
| H8 | Ayuda → Acerca de | Muestra el diálogo y se cierra con Aceptar | ✅ | ✅ |
