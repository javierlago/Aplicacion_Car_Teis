"""The app's look in one place: colour tokens, the Qt palette, the bundled font and the
style sheet.

``styles.qss`` refers to colours as ``@token`` (e.g. ``@accent``); :func:`style_sheet`
replaces them with the values below, so a colour is changed here and nowhere else.
"""

import re
from pathlib import Path

from PyQt6.QtGui import QColor, QFont, QFontDatabase, QPalette
from PyQt6.QtWidgets import QApplication

FONT_FAMILY = "Inter"
FONT_SIZE = 10

COLORS: dict[str, str] = {
    "background": "#E6E9ED",  # window
    "surface": "#FFFFFF",  # cards, fields, tables
    "surface-alt": "#F5F6F8",  # alternating table rows, read-only fields
    "border": "#D0D5DC",
    "border-strong": "#A9B1BB",  # hovered / focused fields
    "text": "#1F2328",
    "muted": "#5F6B7A",  # secondary labels, hints
    "accent": "#F7B500",  # taxi yellow: primary button, selection, active tab
    "accent-hover": "#E0A400",
    "accent-selected": "#FFE38F",  # selected table row
    "accent-soft": "#FFF4D1",  # highlighted values, menu hover
    "danger": "#C62828",
    "danger-soft": "#FDECEC",
    "success": "#2E7D32",
}

_TOKEN = re.compile(r"@([a-z][a-z-]*)")
_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def style_sheet(template: str) -> str:
    """Replace every ``@token`` in ``template``; unknown tokens are an error, not a no-op.

    Comments are dropped first, so they can mention tokens freely.
    """

    def color(match: re.Match[str]) -> str:
        name = match[1]
        if name not in COLORS:
            raise KeyError(f"Unknown colour token @{name} in the style sheet")
        return COLORS[name]

    return _TOKEN.sub(color, _COMMENT.sub("", template))


def palette() -> QPalette:
    """A light palette for the Fusion style, so nothing depends on the Windows theme."""
    c = {name: QColor(value) for name, value in COLORS.items()}
    p = QPalette()
    role, group = QPalette.ColorRole, QPalette.ColorGroup
    for r, name in (
        (role.Window, "background"),
        (role.WindowText, "text"),
        (role.Base, "surface"),
        (role.AlternateBase, "surface-alt"),
        (role.Text, "text"),
        (role.Button, "surface"),
        (role.ButtonText, "text"),
        (role.ToolTipBase, "text"),
        (role.ToolTipText, "surface"),
        (role.PlaceholderText, "muted"),
        (role.Highlight, "accent"),
        (role.HighlightedText, "text"),
        (role.Mid, "border"),
        (role.Midlight, "surface-alt"),
        (role.Dark, "border-strong"),
        (role.Light, "surface"),
    ):
        p.setColor(r, c[name])
    for r in (role.WindowText, role.Text, role.ButtonText):
        p.setColor(group.Disabled, r, c["muted"])
    return p


def load_fonts(font_dir: Path) -> list[str]:
    """Register the bundled fonts; returns the families Qt loaded."""
    families: list[str] = []
    for font_file in sorted(font_dir.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        families += QFontDatabase.applicationFontFamilies(font_id)
    return sorted(set(families))


def apply(app: QApplication, style_template: str, font_dir: Path) -> None:
    load_fonts(font_dir)
    app.setStyle("Fusion")
    app.setPalette(palette())
    font = QFont(FONT_FAMILY, FONT_SIZE)
    font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(font)
    app.setStyleSheet(style_sheet(style_template))
