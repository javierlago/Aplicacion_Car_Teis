"""Sphinx configuration. Build with: sphinx-build -W docs docs/_build/html"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # autodoc imports the Qt modules
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from carteis import __version__  # noqa: E402

project = "CarTeis"
author = "Javier Lago Amoedo"
copyright = f"2023-2026, {author}"
release = __version__
language = "es"

extensions = ["sphinx.ext.autodoc", "sphinx.ext.viewcode"]
autodoc_member_order = "bysource"
autodoc_default_options = {"members": True, "show-inheritance": True}
autodoc_typehints = "description"

exclude_patterns = ["_build"]
html_theme = "alabaster"
html_title = f"CarTeis {release}"
