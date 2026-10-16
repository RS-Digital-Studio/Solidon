"""Die Zahlenzeile vergleicht nur Schritte auf derselben Rechengrundlage (FD-89).

Die Grundlage des gewählten Slicerprofils entsteht im Arbeiter und kommt nach
der ersten Auswertung an. Die Zeile rechnete dann neu und nannte den
Unterschied „seit dem letzten Schritt“, obwohl keiner dazukam — im
Funktionsdurchgang „−2,2 g seit dem letzten Schritt“ an einer unveränderten
Szene. Hier: eine neue Grundlage ohne Schritt meldet nichts, ein Schritt auf
derselben Grundlage nennt seinen Preis, derselbe Stand behält ihn, und eine
Zahl, deren Grundlage noch gelesen wird, sagt „vorläufig“.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from PySide6.QtWidgets import QApplication

from app.core.scene import OperationDraft
from app.core.slice.estimate import Estimate
from app.i18n import tr
from app.ui.facts import PrintFacts
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

_A = Estimate(material_mm3=20_000.0, grams=24.8, seconds=1200.0)
_B = Estimate(material_mm3=12_000.0, grams=14.9, seconds=800.0)


def test_another_basis_sets_the_comparison_quietly(qt_app: QApplication) -> None:
    facts = PrintFacts()
    facts.show_estimate(_A, "p", state=(1,), basis="tabelle")
    facts.show_estimate(_B, "p", state=(1,), basis="slicerprofil")
    assert facts.state()[1] == "", "eine neue Grundlage ist kein Schritt"

    facts.show_estimate(_A, "p", state=(1, 2), basis="slicerprofil")
    assert facts.state()[1].startswith("+"), "ein Schritt auf derselben Grundlage nennt den Preis"


def test_the_same_state_keeps_what_its_step_cost(qt_app: QApplication) -> None:
    """Bild und fertiges Ergebnis desselben Stands, Einheit, Kopfzeile: kein neuer Vergleich."""
    facts = PrintFacts()
    facts.show_estimate(_A, "p", state=(1,), basis="b")
    facts.show_estimate(_B, "p", state=(1, 2), basis="b")
    said = facts.state()[1]
    assert said.startswith("−")
    facts.show_estimate(_B, "p", state=(1, 2), basis="b")
    assert facts.state()[1] == said, "derselbe Stand behält, was sein Schritt gekostet hat"


def test_a_provisional_number_says_so_and_compares_nothing(qt_app: QApplication) -> None:
    facts = PrintFacts()
    facts.show_estimate(_A, "p", state=(1,), basis="tabelle", provisional=True)
    assert facts.state()[1] == tr("vorläufig")
    assert tr("Vorläufig") in facts.toolTip() and tr("Vorläufig") in facts.accessibleDescription()
    facts.show_estimate(_B, "p", state=(1,), basis="slicerprofil")
    assert facts.state()[1] == ""
    assert tr("Vorläufig") not in facts.toolTip()


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    session = Session()
    session.history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 120.0, "depth": 120.0, "height": 60.0})],
    )
    session.evaluate_now()
    built = MainWindow(session, UiSettings())
    yield built
    built.release()


def test_the_window_names_no_step_when_only_the_basis_changed(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg von ``_foundation_found``: neue Grundlage, derselbe Stand."""
    table = window.effective_print_settings()
    profile = replace(table, infill=replace(table.infill, density=1.0))
    monkeypatch.setattr(window, "_foundation_key", lambda quality: "grundlage")
    window._foundation_cache = ("grundlage", object())  # type: ignore[assignment]
    monkeypatch.setattr(window, "effective_print_settings", lambda: table)
    window._update_facts()
    assert window.facts.state()[0] and window.facts.state()[1] == ""

    monkeypatch.setattr(window, "effective_print_settings", lambda: profile)
    window._update_facts()
    summary, delta = window.facts.state()
    assert summary and delta == "", f"ohne Schritt keine Ersparnis: {delta!r}"


def test_the_window_marks_the_number_while_the_basis_is_read(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(window, "_foundation_key", lambda quality: "neu")
    window._foundation_cache = ("alt", object())  # type: ignore[assignment]
    monkeypatch.setattr(window, "_start_foundation", lambda key, quality: None)
    window._update_facts()
    assert window.facts.state()[1] == tr("vorläufig")
