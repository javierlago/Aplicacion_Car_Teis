# PyInstaller build of the desktop app: pyinstaller carteis.spec  ->  dist/CarTeis.exe
#
# Bundled read-only data lands under sys._MEIPASS, where carteis.paths looks for it. The
# user's database is created outside the bundle (in the app data folder) on first run, so
# data survives between runs and upgrades.
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "carteis" / "__main__.py")],
    pathex=[str(ROOT)],
    datas=[
        (str(ROOT / "resources" / "img"), "resources/img"),
        (str(ROOT / "resources" / "styles.qss"), "resources"),
        (str(ROOT / "resources" / "seed.sqlite"), "resources"),
        (str(ROOT / "carteis" / "data" / "migrations" / "*.sql"), "carteis/data/migrations"),
    ],
    excludes=["tkinter", "pytest", "pypdf"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CarTeis",
    console=False,
    upx=False,
    icon=[str(ROOT / "resources" / "img" / "IconTaxi.ico")],
)
