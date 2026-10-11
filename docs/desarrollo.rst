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

No se edita nunca ``carteis/ui/generated/``. Para dar estilo a un widget, se le añade en
Designer una propiedad dinámica ``role`` (por ejemplo ``primary`` o ``field``) y la regla
correspondiente en ``resources/styles.qss``.

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
