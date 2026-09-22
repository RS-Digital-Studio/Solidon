"""Katalogvollständigkeit, Platzhalter und Syntax ohne Import einer Fensterdatei."""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.i18n import SOURCE_LANGUAGE
from app.i18n.catalog import available_languages, read_catalog
from app.i18n.extract import message_ids

paths = (
    "app/core/units.py",
    "app/ui/labels.py",
    "app/ui/analysis_bar.py",
    "app/ui/main_window.py",
    "tests/test_units.py",
    "tests/test_analysis_ui.py",
)
for name in paths:
    ast.parse((ROOT / name).read_text(encoding="utf-8"), filename=name)
print(f"Syntax: {len(paths)} Dateien; Fensterdateien nur geparst, nicht importiert.")

ids = message_ids()
assert ids, "Der Einsammler muss tatsächlich Quellen liefern."
placeholder = re.compile(r"\{([^\W\d]\w*)\}")
languages = [name for name in available_languages() if name != SOURCE_LANGUAGE]
assert languages
for language in languages:
    catalog = read_catalog(language)
    assert set(catalog) == ids, (language, ids - set(catalog), set(catalog) - ids)
    assert all(catalog.values()), language
    for source, translated in catalog.items():
        assert set(placeholder.findall(source)) == set(placeholder.findall(translated)), (
            language, source
        )
    print(f"{language}: {len(catalog)} Quellen vollständig; Platzhalter erhalten.")
