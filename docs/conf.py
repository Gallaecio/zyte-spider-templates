import sys
from pathlib import Path

project = "zyte-spider-templates"
copyright = "2023, Zyte Group Ltd"
author = "Zyte Group Ltd"
release = "0.2.0"

sys.path.insert(0, str(Path(__file__).parent.absolute()))  # _ext
extensions = [
    "_ext",
    "enum_tools.autoenum",
    "sphinx.ext.autodoc",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinxcontrib.autodoc_pydantic",
]

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"

intersphinx_mapping = {
    "python": (
        "https://docs.python.org/3",
        None,
    ),
    "scrapy": (
        "https://docs.scrapy.org/en/latest",
        None,
    ),
    "scrapy-poet": (
        "https://scrapy-poet.readthedocs.io/en/stable",
        None,
    ),
}

autodoc_pydantic_model_show_json = False
