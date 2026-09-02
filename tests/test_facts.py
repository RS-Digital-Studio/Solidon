"""Material und Dauer in der Statusleiste (Bauplan §22, §29).

Die Zahlen selbst prüft ``test_estimate.py``. Hier steht, was der Nutzer davon
sieht — und vor allem, wann die Zeile **schweigt**: eine Anzeige, die bei
jeder Gelegenheit etwas behauptet, wird nach dem dritten Mal nicht mehr
gelesen.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.slice.estimate import Estimate
from app.ui.facts import PrintFacts, change, duration, mass


def test_a_duration_is_said_the_way_a_person_says_it() -> None:
    """Keine Sekunden: eine Schätzung, die auf die Sekunde genau auftritt,
    behauptet eine Genauigkeit, die sie nicht hat."""
    assert duration(0.0) == "0 min"
    assert duration(90.0) == "2 min"
    assert duration(3600.0) == "1 h 0 min"
    assert duration(4500.0) == "1 h 15 min"


def test_grams_lose_their_decimal_when_they_stop_mattering(qt_app: QApplication) -> None:
    """„18,4 g" und „18 g" sind bei einer Schätzung dieselbe Aussage.

    Mit ``qt_app``, obwohl kein Fenster entsteht: Die Fixture setzt ``QLocale``
    auf die Anzeigesprache, und ``mass`` liest von dort das Komma. Ohne sie
    prüfte der Test die Sprache des Rechners — auf dem Linux-Runner stand
    „4.7 g", und ein Worker, in dem noch kein Fenstertest gelaufen war, sah
    es rot (02.09.2026).
    """
    assert mass(4.72) == "4,7 g"
    assert mass(18.4) == "18 g"
    assert "," in mass(9.99), "unter zehn Gramm zählt die Stelle"


def test_the_difference_stays_quiet_when_nothing_happened(qt_app: QApplication) -> None:
    """Eine Zeile, die nach jedem Klick „±0 g" meldet, ist Rauschen."""
    before = Estimate(material_mm3=10_000.0, grams=12.4, seconds=600.0)
    same = Estimate(material_mm3=10_100.0, grams=12.5, seconds=605.0)
    less = Estimate(material_mm3=6_000.0, grams=7.4, seconds=400.0)
    more = Estimate(material_mm3=20_000.0, grams=24.8, seconds=1200.0)

    assert change(None, before) == "", "ohne Vorher gibt es keinen Vergleich"
    assert change(before, same) == "", "ein Zehntelgramm ist kein Ereignis"
    assert change(before, less).startswith("−"), "gespart wird als Minus gezeigt"
    assert change(before, more).startswith("+")
    assert "5,0 g" in change(before, less), "unter zehn Gramm mit Stelle"


def test_an_empty_scene_says_nothing(qt_app: QApplication) -> None:
    """Nicht „0 g": eine Null behauptet, es gäbe etwas zu messen."""
    facts = PrintFacts()
    facts.show_estimate(None)
    assert facts.state() == ("", "")

    facts.show_estimate(Estimate(material_mm3=0.0, grams=0.0, seconds=0.0))
    assert facts.state() == ("", "")


def test_the_line_shows_mass_and_duration(qt_app: QApplication) -> None:
    facts = PrintFacts()
    facts.show_estimate(Estimate(material_mm3=15_000.0, grams=18.6, seconds=4740.0))

    summary, delta = facts.state()
    assert "19 g" in summary or "18 g" in summary
    assert "h" in summary, "die Stunde steht da"
    assert delta == "", "das erste Ergebnis hat nichts, womit es sich vergleicht"


def test_a_second_result_names_the_difference(qt_app: QApplication) -> None:
    """Der eigentliche Gewinn: „hat sich das gelohnt"."""
    facts = PrintFacts()
    facts.show_estimate(Estimate(material_mm3=20_000.0, grams=24.8, seconds=1200.0), "halter.p3d")
    facts.show_estimate(Estimate(material_mm3=12_000.0, grams=14.9, seconds=800.0), "halter.p3d")

    _summary, delta = facts.state()
    assert delta.startswith("−"), f"gespart, also Minus: {delta!r}"
    assert "9,9 g" in delta


def test_another_project_starts_a_new_comparison(qt_app: QApplication) -> None:
    """Sonst meldete das erste Ergebnis eines neuen Projekts eine Ersparnis
    gegenüber dem alten — und die beiden haben nichts miteinander zu tun."""
    facts = PrintFacts()
    facts.show_estimate(Estimate(material_mm3=20_000.0, grams=24.8, seconds=1200.0), "erst.p3d")
    facts.show_estimate(Estimate(material_mm3=12_000.0, grams=14.9, seconds=800.0), "dann.p3d")

    _summary, delta = facts.state()
    assert delta == "", "ein anderes Projekt ist kein Vorher"


def test_the_key_survives_the_first_unsaved_change() -> None:
    """``session.title`` trägt einen Stern, sobald etwas ungesichert ist.

    Als Schlüssel genommen, hätte die Zeile ihren Vergleich genau dann
    verloren, wenn er zum ersten Mal etwas zu sagen hätte — nach der ersten
    Änderung. Deshalb der Pfad.
    """
    from pathlib import Path

    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text("utf-8")
    body = source.split("def _facts_key(", 1)[1].split("\n    def ", 1)[0]
    # Nur der Rumpf, nicht die Erklärung darüber: der Docstring dort nennt
    # ``session.title`` gerade deshalb, weil es im Code nicht stehen darf.
    code = body.split('"""', 2)[-1]
    assert "session.path" in code
    assert "session.title" not in code
