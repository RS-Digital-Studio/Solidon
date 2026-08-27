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
    assert "_show_scene(" in body, (
        "jede Auswertung — auch eine aufgestaute — geht durch _show_scene"
    )

    body = source.split("def _show_scene(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "nach jeder Auswertung"

    body = source.split("def _on_project(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "und bei jedem Projektwechsel"


def test_the_title_names_what_is_open_instead_of_what_is_missing() -> None:
    """„Unbenannt", während der Objektbaum den Namen zeigt.

    **So stand es im Bildschirmfoto des ersten Kunden mit 0.1.3**: oben
    „Unbenannt*", darunter im Baum „GK-Brause" mit seinen Maßen. Der Titel
    wusste den Namen — er sagte ihn nur nicht, sondern nannte stattdessen, was
    fehlt.

    Entschieden von Robert am 23.08.2026: der abgeleitete Name, wie Fusion es
    tut. Ein Titel, der dem Baum widerspricht, ist schlechter als einer, der
    ihn wiederholt.

    **Der Zusatz „(ungespeichert)" bleibt und ist nicht dasselbe wie der
    Stern.** Der Stern sagt „seit dem letzten Speichern geändert", der Zusatz
    sagt „es gibt keine Datei". Ohne ihn sähe „GK-Brause*" aus wie eine
    geöffnete Projektdatei, und der Kunde suchte sie beim nächsten Start.
    """
    session = Session()
    assert session.title == "Unbenannt", "ohne Objekte gibt es nichts abzuleiten"

    _with_object(session, "GK-Brause")
    assert session.title.startswith("GK-Brause"), (
        f"der Baum weiß es, der Titel auch: {session.title}"
    )
    assert "ungespeichert" in session.title, "es gibt keine Datei, und das gehört dazu"


def test_the_derived_name_does_not_leak_into_the_file_dialog() -> None:
    """Der Dateivorschlag nimmt den Namen, nicht den Titel.

    ``main_window`` baut den Vorschlag für *Exportieren* aus dem Titel
    (``safe_name(Path(...).stem)``). Mit dem Zusatz stünde dort
    „GK-Brause (ungespeichert).stl" — ein Dateiname, der eine Eigenschaft des
    Fensters trägt.

    Deshalb zwei Auskünfte statt einer: ``title`` ist für den Menschen,
    ``document_name`` für die Datei.
    """
    session = Session()
    _with_object(session, "GK-Brause")

    assert session.document_name == "GK-Brause"
    assert "ungespeichert" not in session.document_name
    assert "*" not in session.document_name


def _with_object(session: Session, name: str) -> None:
    """Der Sitzung ein Auswertungsergebnis mit einem benannten Körper geben.

    Über das Ergebnis und nicht über das Dokument: Der Titel liest, was
    **dasteht**, und das sind die ausgewerteten Objekte — dieselbe Quelle wie
    der Objektbaum daneben.
    """
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene
    from conftest import make_object

    scene = Scene(objects={"obj_1": make_object(name=name)})
    session.last_result = EvaluationResult(scene=scene)
