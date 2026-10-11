Desarrollo
==========

Instalación
-----------

.. code-block:: sh

    python -m venv .venv
    .venv/Scripts/python -m pip install -e ".[dev]"

Los extras opcionales ``docs`` (Sphinx) y ``build`` (PyInstaller) se instalan igual:
``pip install -e ".[dev,docs,build]"``.

Ejecutar
--------

.. code-block:: sh

    .venv/Scripts/python -m carteis
    CARTEIS_DB=/ruta/copia.sqlite .venv/Scripts/python -m carteis   # sobre otra base de datos

Tests y estilo
--------------

.. code-block:: sh

    .venv/Scripts/python -m pytest --cov        # la cobertura de carteis/ se mantiene al 100 %
    .venv/Scripts/ruff check . && .venv/Scripts/ruff format --check .

Los tests de interfaz abren la ventana real sin pantalla (``QT_QPA_PLATFORM=offscreen``) con
un ``Prompts`` falso, y fallan si algo intenta abrir un diálogo modal de verdad.

Cambiar la interfaz
-------------------

Los ``.ui`` de ``resources/ui/`` se editan con Qt Designer. Después hay que regenerar el
código::

    .venv/Scripts/python tools/build_ui.py

No se edita nunca ``carteis/ui/generated/``.

Distribución:

- Cada formulario es una rejilla (``QGridLayout``) en la que la etiqueta y su campo comparten
  fila; así quedan centrados entre sí. Etiquetas y campos se alinean a la izquierda.
- En cada pestaña, la tarjeta y las tablas crecen hasta el mismo ancho máximo (1160 px) y los
  espaciadores laterales solo ocupan el espacio sobrante, de modo que sus bordes coinciden. Un
  test lo comprueba a 1280×720 y 1600×950.

Estilo y colores
----------------

- Los colores se definen una sola vez en ``carteis/ui/theme.py`` (``COLORS``). En
  ``resources/styles.qss`` se escriben como ``@token`` (``@accent``, ``@text``…); un token que
  no existe es un error al arrancar.
- La app usa el estilo *Fusion* con una paleta propia y la fuente Inter incluida en
  ``resources/fonts``, para verse igual en cualquier equipo.
- Para dar estilo a un widget se le añade en Designer una propiedad dinámica ``role``
  (``field``, ``primary``, ``outline``, ``danger``, ``icon``, ``highlight``, ``total``,
  ``title``, ``table``, ``panel``, ``fare``) y la regla correspondiente en el ``.qss``.
- Los iconos de Lucide se descargan y colorean con ``python tools/fetch_icons.py``.

Cambiar el esquema de la base de datos
--------------------------------------

Se añade un fichero nuevo ``carteis/data/migrations/NNNN_descripcion.sql`` con el siguiente
número. Nunca se modifica una migración ya aplicada: las bases de datos de los usuarios se
actualizan solas al abrir la aplicación.

Generar el ejecutable y la documentación
----------------------------------------

.. code-block:: sh

    .venv/Scripts/pyinstaller carteis.spec           # dist/CarTeis.exe
    .venv/Scripts/sphinx-build -W docs docs/_build/html
