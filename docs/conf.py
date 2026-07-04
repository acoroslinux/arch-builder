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
html_theme = "furo"
html_static_path = ["_static"]
html_title = "Arch-Builder Documentation"
html_theme_options = {
    "navigation_with_keys": True,
    "top_of_page_buttons": ["view"],
    "announcement": "Profile-driven Arch ISO builds with isolated real-mode toolchain support.",
    "light_css_variables": {
        "color-brand-primary": "#a2431f",
        "color-brand-content": "#8a3818",
        "color-api-background": "#f7efe4",
        "color-background-primary": "#f6f0e7",
        "color-background-secondary": "#fffaf3",
        "color-sidebar-background": "#201a16",
        "color-sidebar-background-border": "#3b3028",
        "color-sidebar-link-text": "#f6eee3",
        "color-sidebar-link-text--top-level": "#fff7ea",
        "color-sidebar-item-background--current": "#3a2a20",
        "color-link": "#9b3d1d",
        "color-link--hover": "#6f2912",
        "font-stack": "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif",
        "font-stack--headings": "Space Grotesk, Inter, Segoe UI, sans-serif",
        "font-stack--monospace": "JetBrains Mono, Fira Code, monospace",
        "admonition-font-size": "0.96rem",
        "admonition-title-font-size": "0.96rem",
    },
    "dark_css_variables": {
        "color-brand-primary": "#ff9e6d",
        "color-brand-content": "#ffb38d",
        "color-api-background": "#2a211d",
        "color-background-primary": "#171311",
        "color-background-secondary": "#211b18",
        "color-sidebar-background": "#110d0b",
        "color-sidebar-background-border": "#342923",
        "color-sidebar-link-text": "#f2e7d8",
        "color-sidebar-link-text--top-level": "#fff4e5",
        "color-sidebar-item-background--current": "#34231b",
        "color-link": "#ffb38d",
        "color-link--hover": "#ffd1b6",
    },
}

myst_enable_extensions = [
    "colon_fence",
    "deflist",
]


def setup(app):
    app.add_css_file("custom.css")
    app.add_js_file("mermaid-init.mjs", type="module")