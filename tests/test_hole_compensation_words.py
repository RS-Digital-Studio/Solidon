"""„Materialtoleranz“ ist ein Fachwort — die Bohrung spricht von der Lochkorrektur (FD-7).

Wer aus dem Slicer kommt, versteht nicht, warum die Bohrung größer wird als
getippt, wenn dort „Materialtoleranz berücksichtigen“ steht. Die Maßgruppe
heißt seit FD-7/16/63/64 „Druckabweichung ausgleichen“ und sagt im Satz, was
geschieht; Bohrung setzen, Bohrung verschließen, Langloch, Lochfeld, der
Hinweis nach dem Bohren und das Handbuch sagten weiter „Materialtoleranz“.
Ein Name für alle, und der Satz nennt den Wert so, wie er im Materialprofil
heißt (*Material kalibrieren*: „Lochkorrektur“).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language

LOCALES = Path(__file__).resolve().parent.parent / "app" / "i18n" / "locales"

#: Das Fachwort und seine Übersetzungen, wie sie im Bestand standen.
OLD_WORDS = {
    "de": "Materialtoleranz",
    "en": "material tolerance",
    "es": "tolerancia del material",
    "fr": "tolérance du matériau",
    "it": "tolleranza del materiale",
    "pt": "tolerância do material",
}


def _compensating() -> list[tuple[str, object]]:
    bootstrap.load_operations()
    return [
        (spec.name, entry)
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.name == "compensate"
    ]


def test_every_compensation_has_the_same_plain_name() -> None:
    found = _compensating()
    names = {name for name, _entry in found}
    assert {"drill_hole", "plug_hole", "resize_hole", "slot_hole"} <= names, names
    wrong = [
        f"{name}: {entry.title}"  # type: ignore[attr-defined]
        for name, entry in found
        if str(entry.title) != "Druckabweichung ausgleichen"  # type: ignore[attr-defined]
    ]
    assert not wrong, wrong


@pytest.mark.parametrize("language", available_languages())
def test_no_customer_text_says_material_tolerance(language: str) -> None:
    """Weder der Schlüssel noch seine Übersetzung — auch nicht im Handbuch."""
    if language == "de":
        catalog = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
        texts = list(catalog)
    else:
        catalog = json.loads((LOCALES / f"{language}.json").read_text(encoding="utf-8"))
        texts = list(catalog.values())
    word = OLD_WORDS[language].casefold()
    hits = [text[:80] for text in texts if word in text.casefold()]
    assert not hits, hits


@pytest.mark.parametrize("language", available_languages())
def test_the_drilling_sentence_names_the_hole_compensation(language: str) -> None:
    """Der Satz an *Bohrung setzen* nennt den Wert wie das Materialprofil."""
    install_language(language)
    set_language(language)
    try:
        bootstrap.load_operations()
        drill = {entry.name: entry for entry in REGISTRY.get("drill_hole").params.spec()}
        assert tr("Lochkorrektur").casefold() in str(drill["compensate"].doc).casefold()
        assert tr("Lochkorrektur").casefold() in str(REGISTRY.get("drill_hole").doc).casefold()
    finally:
        set_language("de")


def test_no_code_names_the_tick_by_its_old_title() -> None:
    """Auch kein Kommentar und kein Werkzeug nennt den alten Titel (Review F2a, R8).

    ``scene/fits.py`` beschrieb den Haken als *Materialtoleranz berücksichtigen*,
    nachdem er in der Oberfläche schon „Druckabweichung ausgleichen“ hieß.
    """
    root = Path(__file__).resolve().parent.parent
    old = "Materialtoleranz berücksichtigen"
    hits = [
        f"{path.relative_to(root).as_posix()}:{number}"
        for folder in ("app", "tools")
        for path in sorted((root / folder).rglob("*.py"))
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if old in line
    ]
    assert not hits, hits
