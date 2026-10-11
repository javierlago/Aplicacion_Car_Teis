"""Download the Lucide icons the app uses into resources/img/icons, coloured for the theme.

Run it after adding an icon to ICONS::

    python tools/fetch_icons.py

Lucide is ISC-licensed; the licence is saved next to the icons. Icons are SVGs drawn with
``stroke="currentColor"``; the colour is baked in here because Qt does not apply CSS
colours to SVG images.
"""

import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carteis.ui.theme import COLORS  # noqa: E402

LUCIDE_VERSION = "0.460.0"
BASE_URL = f"https://unpkg.com/lucide-static@{LUCIDE_VERSION}"
OUT_DIR = Path(__file__).resolve().parents[1] / "resources" / "img" / "icons"

# file name in resources/img/icons -> (Lucide icon name, colour token)
ICONS: dict[str, tuple[str, str]] = {
    "chevron-down.svg": ("chevron-down", "muted"),
    # toolbar and menus
    "printer.svg": ("printer", "text"),
    "database-backup.svg": ("database-backup", "text"),
    "archive-restore.svg": ("archive-restore", "text"),
    "eraser.svg": ("eraser", "text"),
    "log-out.svg": ("log-out", "text"),
    "info.svg": ("info", "text"),
    # buttons inside the forms and tables
    "search.svg": ("search", "muted"),
    "calendar.svg": ("calendar", "muted"),
    "eraser-muted.svg": ("eraser", "muted"),
    "trash.svg": ("trash-2", "muted"),
    # DNI check next to the DNI boxes
    "dni-valid.svg": ("circle-check", "success"),
    "dni-invalid.svg": ("circle-x", "danger"),
}

_SVG_START = re.compile(rb"^\s*(<!--.*?-->\s*)?<svg\b", re.DOTALL)


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310 - fixed https URL
        return response.read()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "LICENSE-lucide.txt").write_bytes(fetch(f"{BASE_URL}/LICENSE"))
    for target, (name, token) in ICONS.items():
        svg = fetch(f"{BASE_URL}/icons/{name}.svg")
        if not _SVG_START.match(svg):
            raise ValueError(f"{name}: response is not an SVG")
        svg = svg.replace(b'stroke="currentColor"', f'stroke="{COLORS[token]}"'.encode())
        (OUT_DIR / target).write_bytes(svg)
        print(f"{name} -> {target} ({token})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
