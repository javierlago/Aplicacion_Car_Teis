"""Where the app finds its bundled resources and keeps the user's data.

Nothing here depends on the working directory: resources are located relative to the
package (or to PyInstaller's unpack folder), and data lives in the per-user app data folder.
"""

import os
import shutil
import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths


def _bundle_root() -> Path:
    # PyInstaller unpacks bundled files under sys._MEIPASS; otherwise use the repo root.
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


RESOURCES_DIR = _bundle_root() / "resources"
IMAGES_DIR = _bundle_root() / "img"  # moves to resources/img when the legacy code is removed
STYLE_SHEET = RESOURCES_DIR / "styles.qss"
SEED_DATABASE = RESOURCES_DIR / "seed.sqlite"

DATABASE_ENV = "CARTEIS_DB"  # set it to use another database file (e.g. during development)


def data_dir() -> Path:
    """Per-user folder, e.g. %APPDATA%/CarTeis/CarTeis. Needs the QApplication names set."""
    location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(location)


def database_path() -> Path:
    override = os.environ.get(DATABASE_ENV)
    return Path(override) if override else data_dir() / "carteis.sqlite"


def log_path() -> Path:
    return data_dir() / "logs" / "carteis.log"


def ensure_database(path: Path, seed: Path = SEED_DATABASE) -> Path:
    """Create the user's database from the bundled seed the first time the app runs."""
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(seed, path)
    return path
