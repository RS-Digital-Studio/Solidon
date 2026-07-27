"""Collect translatable texts from the sources (Bauplan §37.2).

Every ``_("…")`` and ``tr("…")`` in the code is a message id. This script gathers
them and updates the catalog files: new ids appear with an empty translation,
disappeared ids are dropped, existing translations stay untouched.

    python -m app.i18n.extract
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.i18n import SOURCE_LANGUAGE, SUPPORTED_LANGUAGES
from app.i18n.catalog import read_catalog, write_catalog

MARKERS = ("_", "tr")
PACKAGE_DIR = Path(__file__).parent.parent


def message_ids(paths: list[Path] | None = None) -> set[str]:
    """Every literal passed to a translation marker."""
    found: set[str] = set()
    for path in paths or sorted(PACKAGE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in MARKERS or not node.args:
                continue
            first = node.args[0]
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                found.add(first.value)
    return found


def update_catalogs() -> dict[str, tuple[int, int]]:
    """Bring every catalog in line with the sources. Returns (total, missing)."""
    ids = message_ids()
    report: dict[str, tuple[int, int]] = {}
    for language in SUPPORTED_LANGUAGES:
        if language == SOURCE_LANGUAGE:
            continue
        existing = read_catalog(language)
        entries = {key: existing.get(key, "") for key in ids}
        write_catalog(language, entries)
        report[language] = (len(entries), sum(1 for value in entries.values() if not value))
    return report


if __name__ == "__main__":
    for language, (total, missing) in update_catalogs().items():
        print(f"{language}: {total} Texte, davon {missing} ohne Übersetzung")
