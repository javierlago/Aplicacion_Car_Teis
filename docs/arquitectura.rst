Arquitectura
============

El paquete ``carteis`` está dividido en capas. Las dependencias van en un solo sentido::

    ui  ──►  services  ──►  domain  ◄──  data
                  │                       ▲
                  └──►  reports           │
                  └───────────────────────┘

``domain``
    Reglas de negocio en Python puro, sin Qt ni SQL. Las entidades (``Driver``, ``Client``,
    ``Invoice``, ``Trip``) son *dataclasses* que se validan al crearse, así que nunca existe
    un objeto inválido. Aquí están también los validadores (DNI/NIE, teléfono, importes), el
    cálculo de tarifas y totales con ``Decimal`` y el formato español de fechas y dinero.
    Los errores son subclases de ``DomainError`` con el mensaje listo para el usuario.

``data``
    Acceso a SQLite con ``sqlite3``. Las claves foráneas están activadas, las escrituras de
    varias sentencias van dentro de ``transaction()`` y los repositorios nunca hacen *commit*
    por su cuenta. El esquema se versiona con migraciones SQL numeradas
    (``PRAGMA user_version``). Fechas en ISO, dinero en céntimos enteros y localidades como
    clave foránea a la tabla de municipios.

``services``
    Los casos de uso que llama la interfaz: altas, bajas y reactivaciones, facturación,
    copias de seguridad, Excel e informes. Comprueban las reglas que implican varios
    registros (por ejemplo, que no se facture a un cliente dado de baja).

``reports``
    Los PDF con reportlab: una plantilla común (cabecera, logo, pie, saltos de página) y una
    función por informe. Reciben objetos del dominio y no saben nada de Qt ni de la base de
    datos.

``ui``
    Un controlador por pestaña sobre el código que genera ``pyuic6`` a partir de los ``.ui``.
    Los controladores no abren ventanas modales directamente: todo pasa por ``Prompts``, de
    modo que los tests pueden sustituirlo. El aspecto lo definen ``carteis/ui/theme.py``
    (colores, paleta y fuente) y ``resources/styles.qss``.

Datos del usuario
-----------------

La base de datos se guarda en la carpeta de datos del usuario
(``%APPDATA%\CarTeis\CarTeis\carteis.sqlite`` en Windows) y se crea a partir de
``resources/seed.sqlite`` la primera vez que se abre la aplicación. Los informes se guardan
en ``Documentos\CarTeis``. Con la variable de entorno ``CARTEIS_DB`` se puede usar otro
fichero de base de datos.

Las copias de seguridad son ficheros ``.zip`` con la base de datos. Al restaurar se valida el
contenido antes de tocar nada, y las copias hechas con la versión original de la aplicación
se convierten automáticamente al esquema nuevo.
