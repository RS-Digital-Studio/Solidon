"""Material und Dauer in der Statusleiste (Bauplan §22, §29).

Die Zahlen selbst prüft ``test_estimate.py``. Hier steht, was der Nutzer davon
sieht — und vor allem, wann die Zeile **schweigt**: eine Anzeige, die bei
jeder Gelegenheit etwas behauptet, wird nach dem dritten Mal nicht mehr
gelesen.
"""

from __future__ import annotations

from pathlib import Path

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


def test_the_facts_are_a_keyboard_button(qt_app: QApplication) -> None:
    """Die klickbare Statusauskunft trägt Rolle und Tastaturweg eines Knopfs."""

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QAccessible
    from PySide6.QtTest import QTest

    facts = PrintFacts()
    interface = QAccessible.queryAccessibleInterface(facts)
    assert interface is not None and interface.role() == QAccessible.Role.Button
    seen: list[bool] = []
    facts.clicked.connect(lambda: seen.append(True))

    facts.setFocus()
    QTest.keyClick(facts, Qt.Key.Key_Return)

    assert seen == [True]


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


def test_the_window_compares_within_a_project_and_never_across(
    qt_app: QApplication, tmp_path: Path
) -> None:
    """Im gebauten Fenster: Eine Änderung nennt die Differenz, ein anderes Projekt nicht.

    Hier stand eine Prüfung auf den **Quelltext** von ``_facts_key`` — ob der
    Pfad darin vorkommt und ``session.title`` nicht. Die Methode rief niemand
    auf: ``_update_facts`` gab gar keinen Schlüssel weiter, und der Vergleich
    fiel beim Öffnen nur weg, weil ``_reset_for`` zufällig vorher ein leeres
    Ergebnis meldete (22.09.2026). Jetzt geht der Weg durchs Fenster: öffnen,
    ändern — die Zeile nennt die Differenz, trotz Stern im Titel —, ein
    zweites Projekt öffnen, und die Zeile schweigt.
    """
    from app.core.scene import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    for name, width in (("klein.p3d", 20.0), ("gross.p3d", 60.0)):
        session = Session()
        session.history.apply("Quader", [OperationDraft(op="create_box", params={"width": width})])
        session.evaluate_now()
        session.save_project(tmp_path / name)
        session.release()

    window = MainWindow(Session(), UiSettings())
    try:
        window.open_path(tmp_path / "klein.p3d")
        assert window.session.wait_for_idle(30_000)
        QApplication.processEvents()
        ops = window.session.project.document.ops
        box = next(entry for entry in ops if entry.op == "create_box")
        assert window.session.change_params(int(box.id), {**box.params, "width": 40.0})
        assert window.session.wait_for_idle(30_000)
        QApplication.processEvents()
        assert window.session.title.endswith("*"), "ungesichert — der Titel trägt den Stern"
        _summary, delta = window.facts.state()
        assert delta.startswith("+"), f"die Änderung nennt ihren Preis: {delta!r}"
        # Gesichert, sonst fragt das Öffnen nach — und der Dialog wartete
        # offscreen auf niemanden.
        window.session.save_project(tmp_path / "klein.p3d")

        window.open_path(tmp_path / "gross.p3d")
        assert window.session.wait_for_idle(30_000)
        QApplication.processEvents()
        summary, delta = window.facts.state()
        assert summary, "das neue Projekt hat eine Zahl"
        assert delta == "", "ein anderes Projekt ist kein Vorher"

        # Und direkt, ohne das leere Ergebnis dazwischen, auf das sich der
        # alte Weg verließ: Die Zeile erkennt den Wechsel am Schlüssel.
        window.facts.show_estimate(Estimate(material_mm3=1.0, grams=99.0, seconds=60.0), "vorher")
        window._update_facts()
        assert window.facts.state()[1] == "", "der Schlüssel trennt die Projekte"
    finally:
        window.release()
