import re

import pytest
from PyQt6.QtGui import QFontDatabase, QPalette

from carteis import paths
from carteis.ui import theme


def test_tokens_are_replaced():
    assert theme.style_sheet("a { color: @text; background: @accent-soft; }") == (
        f"a {{ color: {theme.COLORS['text']}; background: {theme.COLORS['accent-soft']}; }}"
    )


def test_unknown_token_is_an_error():
    with pytest.raises(KeyError, match="@nope"):
        theme.style_sheet("a { color: @nope; }")


def test_comments_may_mention_tokens():
    assert theme.style_sheet("/* use @whatever */ a { color: @text; }") == (
        f" a {{ color: {theme.COLORS['text']}; }}"
    )


def test_bundled_style_sheet_uses_only_known_tokens():
    css = theme.style_sheet(paths.STYLE_SHEET.read_text(encoding="utf-8"))
    assert "@" not in css
    assert re.search(r"#[0-9A-F]{6}", css)


def test_palette_does_not_follow_the_system_theme():
    palette = theme.palette()
    role = QPalette.ColorRole
    assert palette.color(role.Window).name().upper() == theme.COLORS["background"]
    assert palette.color(role.Highlight).name().upper() == theme.COLORS["accent"]
    disabled = palette.color(QPalette.ColorGroup.Disabled, role.Text)
    assert disabled.name().upper() == theme.COLORS["muted"]


def test_bundled_font_loads(qapp):
    assert "Inter" in theme.load_fonts(paths.FONTS_DIR)
    assert "Inter" in QFontDatabase.families()


def test_apply(qapp, monkeypatch):
    styles = []
    monkeypatch.setattr(qapp, "setStyle", styles.append)  # Fusion would stay for later tests
    font, palette = qapp.font(), qapp.palette()
    try:
        theme.apply(qapp, "QLabel { color: @text; }", paths.FONTS_DIR)
        assert styles == ["Fusion"]
        assert qapp.font().family() == "Inter"
        assert theme.COLORS["text"] in qapp.styleSheet()
    finally:
        qapp.setStyleSheet("")
        qapp.setFont(font)
        qapp.setPalette(palette)
