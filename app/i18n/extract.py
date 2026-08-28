"""Übersetzbare Texte aus den Quellen einsammeln (Bauplan §37.2).

Jedes ``_("…")`` und ``tr("…")`` im Code ist eine Message-ID. Dieses Skript
sammelt sie und zieht die Katalogdateien nach: neue IDs erscheinen mit leerer
Übersetzung, verschwundene fliegen raus, bestehende Übersetzungen bleiben
unangetastet.

    python -m app.i18n.extract
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.i18n import SOURCE_LANGUAGE
from app.i18n.catalog import available_languages, read_catalog, write_catalog

MARKERS = ("_", "tr")
PACKAGE_DIR = Path(__file__).parent.parent

#: Quellen außerhalb des Pakets, deren Message-IDs trotzdem ausgeliefert
#: werden: die Transaktionstitel der Beispiel-Bauer reisen in den erzeugten
#: ``.p3d``-Dateien mit und müssen im Katalog stehen, sonst zeigt der Verlauf
#: sie unübersetzt.
# ``make_figures`` steht hier aus demselben Grund wie ``make_examples``: Es
# schreibt Oberflächentexte in Bilder, die der Kunde sieht — ein ``tr()``, das
# die Sammlung nicht kennt, fällt in fünf Sprachen still auf Deutsch zurück
# („Halter für die Werkbank" stand auf jedem fremdsprachigen own-part-Bild).
EXTRA_SOURCES = (
    PACKAGE_DIR.parent / "tools" / "make_examples.py",
    PACKAGE_DIR.parent / "tools" / "make_figures.py",
    PACKAGE_DIR.parent / "tools" / "make_changelog.py",
)


def message_ids(paths: list[Path] | None = None) -> set[str]:
    """Jedes Literal, das an einen Übersetzungsmarker übergeben wird."""
    found: set[str] = set()
    for path in paths or (*sorted(PACKAGE_DIR.rglob("*.py")), *EXTRA_SOURCES):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            if node.func.id not in MARKERS or not node.args:
                continue
            first = node.args[0]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            # Das zweite Argument ist der Kontext, und mit ihm schlägt
            # ``TranslatableText`` unter ``Kontext + chr(4) + Text`` nach —
            # ein Aufruf mit Kontext bliebe sonst in jeder Sprache deutsch,
            # und die Übersetzungsprüfung (dieselbe Sammlung) merkte nichts
            # (Gesamtreview L-9).
            context = None
            if len(node.args) > 1:
                second = node.args[1]
                if isinstance(second, ast.Constant) and isinstance(second.value, str):
                    context = second.value
            for keyword in node.keywords:
                if (
                    keyword.arg == "context"
                    and isinstance(keyword.value, ast.Constant)
                    and isinstance(keyword.value.value, str)
                ):
                    context = keyword.value.value
            found.add(context + chr(4) + first.value if context else first.value)
    return found


def update_catalogs() -> dict[str, tuple[int, int]]:
    """Bringt jeden Katalog auf den Stand der Quellen. Liefert (gesamt, offen)."""
    ids = message_ids()
    report: dict[str, tuple[int, int]] = {}
    for language in available_languages():
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
