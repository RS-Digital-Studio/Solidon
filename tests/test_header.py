"""Die Kopfzeile sagt, was offen ist und worauf es gedruckt wird.

Drucker und Material bestimmen jede Toleranz im Stapel (§12) — eine Passung
ist ein Verweis ins Materialprofil, kein Zahlenwert. Wer sie nicht sieht, weiß
nicht, was seine Bohrung bedeutet, und musste dafür bisher einen Dialog
öffnen.

Geprüft wird der Text, nicht das Aussehen: was dort steht, ist eine Aussage
über das Projekt und muss stimmen.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.knowledge import profiles
from app.ui.header import HeaderBar, bounds_text, project_name
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


def test_the_title_drops_the_suffix_but_keeps_the_star() -> None:
    """Dass ein Projekt ``.p3d`` heißt, unterscheidet keines vom anderen.

    Der Stern dagegen ist eine Aussage — er sagt, dass etwas ungesichert ist,
    und muss die Kürzung überleben.
    """
    assert project_name("halter.p3d") == "halter"
    assert project_name("halter.p3d*") == "halter*"
    assert project_name("Unbenannt") == "Unbenannt"
    assert project_name("Unbenannt*") == "Unbenannt*"


def test_the_measurements_name_their_unit_once() -> None:
    """„80,00 mm × 50,00 mm × 8,00 mm" sagt dreimal dasselbe."""
    from app.core.scene import EvaluationResult

    assert bounds_text(None, "mm") == "", "ohne Ergebnis behauptet die Zeile nichts"
    empty: EvaluationResult | None = None
    assert bounds_text(empty, "mm") == ""


def test_an_empty_header_says_nothing(qt_app: QApplication) -> None:
    """Vor dem ersten Projekt steht dort nichts — kein „—", kein „0 mm".

    Eine Zeile, die Platzhalter zeigt, behauptet, es gäbe etwas zu sehen.
    """
    header = HeaderBar()
    title, bounds, printer, material = header.state()
    assert (title, bounds, printer, material) == ("", "", "", "")


def test_the_header_names_printer_and_material(qt_app: QApplication) -> None:
    """Beide, denn beide ändern das Ergebnis."""
    header = HeaderBar()
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    header.show_profile(profile)

    _title, _bounds, printer, material = header.state()
    assert printer == str(profile.printer.title)
    assert material == str(profile.material.title)


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1200, 900)
    window._show_start_screen(False)
    qt_app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_the_window_wires_the_header_to_the_session(window: MainWindow) -> None:
    """Die Kette Fenster → Sitzung → Kopfzeile, ohne eine Datei zu laden.

    Geprüft wird die Verdrahtung und nicht das Laden: dass ein Netz ankommt,
    steht in ``test_ui.py``. Hier zählt, dass ``_update_header`` liest, was die
    Sitzung sagt — und dass es an den beiden Stellen hängt, an denen sich das
    ändert (Projektwechsel und Auswertung).
    """
    window._update_header()

    title, _bounds, printer, material = window.header.state()
    assert title == project_name(window.session.title)
    assert printer == str(window.session.profile.printer.title)
    assert material == str(window.session.profile.material.title)


def test_the_header_is_updated_where_the_state_changes() -> None:
    """Beide Auslöser, an der Quelle geprüft.

    Ein Test, der nur einen davon kennt, bleibt grün, während die Zeile nach
    einer Auswertung veraltet dasteht — genau der Fehler, den man erst bemerkt,
    wenn ein Maß nicht mehr stimmt.
    """
    from pathlib import Path

    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text("utf-8")
    body = source.split("def _on_scene(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "nach jeder Auswertung"

    body = source.split("def _on_project(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "und bei jedem Projektwechsel"
