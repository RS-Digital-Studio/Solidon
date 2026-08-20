"""Nur die HTML-Seiten des Handbuchs neu schreiben — Abbildungen und PDF bleiben.

Die Abbildungen liegen unverändert unter ``website/handbuch/<sprache>/``; an
ihnen ändert der Ankerfehler nichts. Das PDF entsteht beim Ausliefern aus
derselben Seite.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from app.core import figures
from app.core.bootstrap import load_operations
from app.i18n import install_catalog, set_language
from app.i18n.catalog import read_catalog
from tools.make_manual import PAGES, WEBSITE, page_for, page_html

load_operations()
for language in PAGES:
    install_catalog(language, read_catalog(language))
    set_language(language)
    figures.forget()
    name, prefix = page_for(language)
    target = WEBSITE / name
    target.write_text(page_html(language, prefix), encoding="utf-8")
    print(f"{language}: {target.relative_to(Path.cwd())}")
set_language("de")
