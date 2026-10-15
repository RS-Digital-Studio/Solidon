"""Das vorbereitete Fenster der Wortschatzfälle (``test_guide_targets.py``).

Ein eigenes Modul statt ``ui_helpers.py``: Nur diese eine Testdatei braucht es,
und ``ui_helpers`` importieren Dutzende Fensterdateien, die die Auswahl sonst
für jede Änderung hier mitnähme (``tests.md``).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QMenu

from app.core.scene.history import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


def at_rest(window: Any) -> bool:
    """Ob keine Seitenkarte mehr gleitet und kein Setzen der Zonen vorgemerkt ist.

    Eine Karte gleitet ``overlay.MOVE_MS`` zu ihrem Platz; wer währenddessen
    liest, sieht eine Zwischenlage, die der Kunde nach dem Gleiten nicht mehr
    hat — und wie weit die Bewegung in einer festen Zahl Ereignisrunden kommt,
    hängt an der Rechnerlast (FD-157).
    """
    overlay = window.overlay
    return not overlay._moves and overlay._pending is None


def settle(qt_app: QApplication, rounds: int = 20) -> None:
    """Ereignisse zustellen, bis jedes gezeigte Hauptfenster still steht.

    Erst die festen Runden (Listen legen ihre Zeilen über Nullzeitgeber), dann
    auf den Zustand warten, nicht Runden zählen. Gewartet wird mit
    ``processEvents`` und ``time.sleep``: die Bewegung braucht Wanduhrzeit.
    """
    for _ in range(rounds):
        qt_app.processEvents()
    windows = [
        widget
        for widget in qt_app.topLevelWidgets()
        if isinstance(widget, MainWindow) and widget.isVisible()
    ]
    deadline = time.monotonic() + 60
    while not all(at_rest(window) for window in windows) and time.monotonic() < deadline:
        qt_app.processEvents()
        time.sleep(0.01)
    assert all(at_rest(window) for window in windows), "eine Seitenkarte gleitet nach 60 s noch"


@pytest.fixture
def prepared_window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster mit einem Quader samt Bohrung, unter das Bett geschoben, im
    Aussehen des Kunden — für den Wortschatz des Funktionsdurchgangs.

    Die Attrappe des Renderers gibt der Ansicht eine Projektion; offscreen gibt
    es sonst keine, und die Maßgruppe im Bild bliebe aus. Das Thema setzt
    ``app.py`` vor dem ersten Fenster; es ändert Zeilenhöhen und damit, ob eine
    Zeile ganz dasteht. Zurück gibt es ``conftest.py``. Übergeben wird das
    Fenster erst, wenn die Karten nach dem Ergebnis still stehen (:func:`settle`).
    """
    from app.ui.theme import apply_theme
    from tests.render_fakes import RecordingRenderer
    from tools.function_checks import SMALLEST_WINDOW

    apply_theme(qt_app, UiSettings().theme)
    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(*SMALLEST_WINDOW)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
            OperationDraft(
                op="translate_object", inputs=("obj_1",), params={"dx": 0.0, "dy": 0.0, "dz": -15.0}
            ),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    window.report.show_result(window.session.last_result, window.session.project.document)
    settle(qt_app)
    try:
        yield window
    finally:
        for menu in [*window.findChildren(QMenu), *qt_app.topLevelWidgets()]:
            if isinstance(menu, QMenu) and menu.isVisible():
                menu.hide()
        window.hide()
        window.release()
        window.viewport.renderer = None
