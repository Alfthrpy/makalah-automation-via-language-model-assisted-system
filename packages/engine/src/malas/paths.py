"""Lokasi berkas yang ikut paket (template dokumen & contoh input), terlepas dari working directory."""
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = PACKAGE_DIR / "templates"
EXAMPLES_DIR = PACKAGE_DIR / "examples"
DEFAULT_TEMPLATE_NAME = "template makalah.docx"
DEFAULT_TEMPLATE = TEMPLATES_DIR / DEFAULT_TEMPLATE_NAME
DEFAULT_INPUT = EXAMPLES_DIR / "contoh.yaml"
