"""Formsprache: Stylesheet, Typografie-Skala, Abstandsraster (§19.3).

„Sieht standard aus" ist kein Geschmacksurteil, sondern hat nachweisbare
Ursachen — keine Formsprache, keine Typografie-Skala, kein Abstandsrhythmus.
Diese Datei hält die drei Antworten darauf fest, damit sie nicht wieder
auseinanderlaufen: eine Gestaltung, die an fünfzig Einzelstellen entschieden
wird, ist nach zehn Änderungen keine mehr.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from app.ui.style import LEVELS, NORMAL, ROOMY, SPACE, TIGHT, WIDE, stylesheet, type_scale
from app.ui.theme import THEMES

UI = Path(__file__).parent.parent / "app" / "ui"


def test_the_scale_gets_quieter_step_by_step() -> None:
    """Vier Stufen, und jede leiser als die davor.

    Vorher war alles gleich laut: im Objektbaum war der Name so groß wie das
    Maß, im Prüfbericht ein Fehler so groß wie ein Hinweis. Eine Skala, deren
    Stufen sich überschneiden, wäre wieder keine.
    """
    sizes = type_scale(10)
    assert list(sizes) == list(LEVELS)

    values = [sizes[level][0] for level in LEVELS]
    assert values == sorted(values, reverse=True), f"nicht absteigend: {values}"
    assert len(set(values)) == len(values), "zwei Stufen gleich groß sind eine Stufe"

    assert sizes["caption"][1] < sizes["section"][1], "Nebentext soll nicht mitreden"


def test_the_scale_follows_the_system_font() -> None:
    """§19.3 verlangt skalierbare Schrift: wer seine Systemschrift größer
    stellt, bekommt die ganze Anwendung größer, nicht nur den Rest."""
    small = type_scale(8)
    large = type_scale(16)
    for level in LEVELS:
        assert large[level][0] > small[level][0], level


def test_the_grid_is_one_number_and_its_multiples() -> None:
    for step in (TIGHT, NORMAL, ROOMY, WIDE):
        assert step % SPACE == 0
    assert TIGHT < NORMAL < ROOMY < WIDE


#: ``setSpacing(…)`` und ``setContentsMargins(…)`` mit nackten Zahlen.
_SPACING = re.compile(r"set(?:Spacing|ContentsMargins)\(([^)]*)\)")


def test_no_layout_invents_its_own_distance() -> None:
    """Elemente standen mal 2, mal 3, mal 5, mal 6 Pixel auseinander.

    Das ist der Eindruck, dass alles ein bisschen daneben sitzt, ohne dass man
    einen einzelnen Fehler benennen kann. Null bleibt erlaubt: kein Abstand ist
    eine Aussage, kein Zwischenwert.
    """
    off: dict[str, list[str]] = {}
    for path in sorted(UI.glob("*.py")):
        for match in _SPACING.finditer(path.read_text(encoding="utf-8")):
            for part in match.group(1).split(","):
                value = part.strip()
                if not value.isdigit() or int(value) == 0:
                    continue
                if int(value) % SPACE:
                    off.setdefault(path.name, []).append(match.group(0))

    assert not off, (
        f"Diese Abstände liegen nicht auf dem Raster von {SPACE} px: {off}. "
        "TIGHT, NORMAL, ROOMY und WIDE aus app/ui/style.py sind die Stufen."
    )


def test_the_stylesheet_covers_the_states_a_control_has() -> None:
    """Ein Knopf, den man nicht überfahren sieht, fühlt sich tot an.

    Fusion bringt Zustände mit; sobald ein Stylesheet ein Element anfasst,
    bringt es keine mehr. Wer also stylt, muss alle vier liefern.
    """
    sheet = stylesheet("dark", 10)
    for state in (":hover", ":focus", ":pressed", ":disabled"):
        assert state in sheet, f"kein Zustand {state} im Stylesheet"

    assert "QPushButton:default" in sheet, "Haupt- und Nebenknopf müssen sich unterscheiden"


def test_both_themes_build_a_stylesheet_out_of_their_own_colours() -> None:
    """Ein Themenwechsel, der nur die Palette umstellt, lässt die Form stehen —
    und die Form trägt hier Farben."""
    sheets = {}
    for theme in THEMES:
        sheets[theme] = stylesheet(theme, 10)
        assert THEMES[theme]["highlight"] in sheets[theme]
        assert THEMES[theme]["base"] in sheets[theme]

    assert len(set(sheets.values())) == len(THEMES), "zwei Themen, ein Aussehen"


def test_a_size_is_never_hardcoded_in_the_sheet() -> None:
    """Die Stufen kommen aus der Skala, nicht aus der Datei."""
    sheet = stylesheet("dark", 10)
    sizes = {size for size, _weight in type_scale(10).values()}
    for match in re.finditer(r"font-size:\s*(\d+)pt", sheet):
        assert int(match.group(1)) in sizes, f"{match.group(0)} steht in keiner Stufe"
