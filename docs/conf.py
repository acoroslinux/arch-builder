from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

project = "Arch-Builder"
author = "Arch-Builder contributors"
copyright = "2026, Arch-Builder contributors"
release = "1.0"

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
master_doc = "index"
html_theme = "classic"
html_static_path = ["_static"]
html_title = "Arch-Builder Documentation"

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]


def setup(app):
    app.add_css_file("custom.css")
    app.add_js_file("mermaid-init.mjs", type="module")